from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi.responses import JSONResponse, RedirectResponse
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession
from urllib.parse import quote, urlparse

from app.core.config import Settings, get_settings
from app.core.cookies import REFRESH_COOKIE_NAME, clear_refresh_cookie, set_refresh_cookie
from app.core.dependencies import get_auth_service, get_current_active_user, get_db, get_redis
from app.core.exceptions import AppError
from app.middleware.rate_limit import apply_rate_limit
from app.models.user import User
from app.schemas.auth import (
    AuthStatusResponse,
    GoogleLoginResponse,
    GoogleOAuthConfigResponse,
    LogoutResponse,
    RefreshTokenRequest,
    SessionExchangeRequest,
    TokenResponse,
    UserPublic,
)
from app.services.auth_service import AuthService
from app.utils.oauth_redirect import (
    is_allowed_dev_origin,
    is_private_lan_origin,
    list_dev_authorized_origins,
    list_dev_redirect_uris,
    normalize_origin,
    resolve_dev_oauth_redirect_uri,
)

router = APIRouter()


def _allowed_frontend_origins(settings: Settings) -> set[str]:
    allowed = {settings.FRONTEND_URL.rstrip("/"), *settings.cors_origins}
    return {o.rstrip("/") for o in allowed if o}


def _resolve_oauth_context(
    settings: Settings,
    *,
    origin: str | None,
) -> tuple[str, str]:
    """Return (redirect_uri, frontend_url) for the current sign-in request.

    Production / public SPA (Vercel): stable BACKEND_PUBLIC_URL callback +
    FRONTEND_URL (or a CORS-listed origin).

    Local LAN phones: callback must hit the same private host as the SPA
    (Vite proxies /api), because localhost on the phone is not this PC.
    """
    default_frontend = settings.FRONTEND_URL.rstrip("/")

    if settings.is_production:
        redirect_uri = settings.google_oauth_redirect_uri
        if origin:
            try:
                normalized = normalize_origin(origin)
            except ValueError:
                return redirect_uri, default_frontend
            if normalized in _allowed_frontend_origins(settings):
                return redirect_uri, normalized
        return redirect_uri, default_frontend

    redirect_uri = resolve_dev_oauth_redirect_uri(
        origin=origin,
        backend_redirect_uri=settings.google_oauth_redirect_uri,
        api_prefix=settings.API_V1_PREFIX,
    )

    if origin:
        try:
            normalized = normalize_origin(origin)
        except ValueError:
            return redirect_uri, default_frontend
        if is_allowed_dev_origin(origin) or normalized in _allowed_frontend_origins(settings):
            return redirect_uri, normalized

    return redirect_uri, default_frontend


@router.get("/google/login", response_model=GoogleLoginResponse)
@apply_rate_limit("20/minute")
async def google_login(
    request: Request,
    origin: str | None = Query(default=None),
    redis: Redis = Depends(get_redis),
    auth_service: AuthService = Depends(get_auth_service),
    settings: Settings = Depends(get_settings),
) -> GoogleLoginResponse:
    _ = request
    redirect_uri, frontend_url = _resolve_oauth_context(settings, origin=origin)
    url, state = await auth_service.create_google_login_url(
        redis,
        redirect_uri=redirect_uri,
        frontend_url=frontend_url,
    )
    return GoogleLoginResponse(authorization_url=url, state=state)


@router.get("/google/login/redirect")
@apply_rate_limit("20/minute")
async def google_login_redirect(
    request: Request,
    origin: str | None = Query(default=None),
    redis: Redis = Depends(get_redis),
    auth_service: AuthService = Depends(get_auth_service),
    settings: Settings = Depends(get_settings),
):
    """Browser navigation entrypoint — avoids fetch/CORS issues during OAuth."""
    _ = request
    redirect_uri, frontend_url = _resolve_oauth_context(settings, origin=origin)
    url, _state = await auth_service.create_google_login_url(
        redis,
        redirect_uri=redirect_uri,
        frontend_url=frontend_url,
    )
    return RedirectResponse(url=url, status_code=302)


@router.get("/google/oauth-config", response_model=GoogleOAuthConfigResponse)
@apply_rate_limit("60/minute")
async def google_oauth_config(
    request: Request,
    origin: str | None = Query(default=None),
    settings: Settings = Depends(get_settings),
) -> GoogleOAuthConfigResponse:
    """Development helper: shows the exact redirect URI registered with Google."""
    _ = request
    if settings.is_production:
        raise AppError("Not found", status_code=404)

    frontend_port = urlparse(settings.FRONTEND_URL).port or 5173
    required = list_dev_redirect_uris(
        frontend_port=frontend_port,
        backend_port=settings.PORT,
    )
    # Always include the live configured callback (Vercel / tunnel / custom).
    live_callback = settings.google_oauth_redirect_uri
    if live_callback not in required:
        required.insert(0, live_callback)

    authorized = list_dev_authorized_origins(frontend_port=frontend_port)
    live_frontend = settings.FRONTEND_URL.rstrip("/")
    if live_frontend not in authorized:
        authorized.insert(0, live_frontend)
    for cors_origin in settings.cors_origins:
        if cors_origin and cors_origin not in authorized:
            authorized.append(cors_origin)

    candidate = origin or request.headers.get("origin")
    if candidate:
        try:
            normalized = normalize_origin(candidate)
            if normalized not in authorized:
                authorized.append(normalized)
            if is_allowed_dev_origin(candidate) and is_private_lan_origin(normalized):
                lan_callback = (
                    f"{normalized}{settings.API_V1_PREFIX.rstrip('/')}/auth/google/callback"
                )
                if lan_callback not in required:
                    required.append(lan_callback)
        except ValueError:
            pass

    return GoogleOAuthConfigResponse(
        redirect_uri=settings.google_oauth_redirect_uri,
        backend_public_url=settings.BACKEND_PUBLIC_URL,
        frontend_callback_url=f"{settings.FRONTEND_URL.rstrip('/')}/auth/callback",
        google_configured=bool(settings.GOOGLE_CLIENT_ID and settings.GOOGLE_CLIENT_SECRET),
        required_redirect_uris=required,
        authorized_origins=authorized,
        google_console_url=(
            f"https://console.cloud.google.com/apis/credentials/oauthclient/{settings.GOOGLE_CLIENT_ID}"
            if settings.GOOGLE_CLIENT_ID
            else "https://console.cloud.google.com/apis/credentials"
        ),
    )


@router.post("/google/reconnect", response_model=GoogleLoginResponse)
@apply_rate_limit("10/minute")
async def google_reconnect(
    request: Request,
    origin: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    auth_service: AuthService = Depends(get_auth_service),
    settings: Settings = Depends(get_settings),
    current_user: User = Depends(get_current_active_user),
) -> GoogleLoginResponse:
    """Revoke stale Gmail tokens and return a fresh Google consent URL."""
    _ = request
    account_email = await auth_service.prepare_gmail_reconnect(db, current_user)
    redirect_uri, frontend_url = _resolve_oauth_context(settings, origin=origin)
    url, state = await auth_service.create_google_login_url(
        redis,
        login_hint=account_email,
        redirect_uri=redirect_uri,
        frontend_url=frontend_url,
    )
    return GoogleLoginResponse(authorization_url=url, state=state)


@router.get("/google/callback")
@apply_rate_limit("30/minute")
async def google_callback(
    request: Request,
    code: str = Query(...),
    state: str = Query(...),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    auth_service: AuthService = Depends(get_auth_service),
    settings: Settings = Depends(get_settings),
):
    _ = request
    frontend_url = settings.FRONTEND_URL.rstrip("/")
    try:
        oauth_context = await auth_service.validate_oauth_state(redis, state)
        frontend_url = oauth_context.frontend_url.rstrip("/")
        google_tokens, google_user = await auth_service.exchange_google_code(
            code,
            redirect_uri=oauth_context.redirect_uri,
        )
        user = await auth_service.upsert_user_from_google(db, google_tokens, google_user)
        token_response, refresh_token = await auth_service.create_session(redis, user)
        exchange_code = await auth_service.store_exchange_code(redis, token_response, refresh_token)
        redirect_url = f"{frontend_url}/auth/callback?code={exchange_code}"
        response = RedirectResponse(url=redirect_url, status_code=302)
        set_refresh_cookie(response, refresh_token, secure=settings.is_production)
        return response
    except AppError as exc:
        error_url = f"{frontend_url}/auth/callback?error={quote(exc.message, safe='')}"
        return RedirectResponse(url=error_url, status_code=302)


@router.post("/session/exchange", response_model=TokenResponse)
@apply_rate_limit("30/minute")
async def exchange_session(
    request: Request,
    body: SessionExchangeRequest,
    redis: Redis = Depends(get_redis),
    auth_service: AuthService = Depends(get_auth_service),
    settings: Settings = Depends(get_settings),
) -> JSONResponse:
    _ = request
    token_response, refresh_token = await auth_service.exchange_session_code(redis, body.code)
    response = JSONResponse(content=token_response.model_dump(mode="json"))
    set_refresh_cookie(response, refresh_token, secure=settings.is_production)
    return response


@router.post("/refresh", response_model=TokenResponse)
@apply_rate_limit("60/minute")
async def refresh_tokens(
    request: Request,
    body: RefreshTokenRequest,
    redis: Redis = Depends(get_redis),
    db: AsyncSession = Depends(get_db),
    auth_service: AuthService = Depends(get_auth_service),
    settings: Settings = Depends(get_settings),
) -> JSONResponse:
    refresh_token = body.refresh_token or request.cookies.get(REFRESH_COOKIE_NAME)
    if not refresh_token:
        raise AppError("Refresh token is required", status_code=401)

    token_response, new_refresh_token = await auth_service.refresh_session(redis, db, refresh_token)
    response = JSONResponse(content=token_response.model_dump(mode="json"))
    set_refresh_cookie(response, new_refresh_token, secure=settings.is_production)
    return response


@router.post("/logout", response_model=LogoutResponse)
@apply_rate_limit("30/minute")
async def logout(
    request: Request,
    response: Response,
    body: RefreshTokenRequest | None = None,
    redis: Redis = Depends(get_redis),
    auth_service: AuthService = Depends(get_auth_service),
    settings: Settings = Depends(get_settings),
    _current_user: User = Depends(get_current_active_user),
) -> LogoutResponse:
    refresh_token = (body.refresh_token if body else None) or request.cookies.get(REFRESH_COOKIE_NAME)
    await auth_service.logout(redis, refresh_token)
    clear_refresh_cookie(response, secure=settings.is_production)
    return LogoutResponse()


@router.get("/me", response_model=UserPublic)
@apply_rate_limit("60/minute")
async def get_me(
    request: Request,
    current_user: User = Depends(get_current_active_user),
) -> UserPublic:
    _ = request
    return UserPublic.model_validate(current_user)


@router.get("/status", response_model=AuthStatusResponse)
@apply_rate_limit("60/minute")
async def auth_status(
    request: Request,
    db: AsyncSession = Depends(get_db),
    auth_service: AuthService = Depends(get_auth_service),
) -> AuthStatusResponse:
    authorization = request.headers.get("Authorization", "")
    if not authorization.lower().startswith("bearer "):
        return AuthStatusResponse(authenticated=False, user=None)

    access_token = authorization.split(" ", 1)[1]
    try:
        user = await auth_service.get_user_from_access_token(db, access_token)
    except AppError:
        return AuthStatusResponse(authenticated=False, user=None)

    return AuthStatusResponse(
        authenticated=True,
        user=UserPublic.model_validate(user),
    )


@router.post("/dev/login", response_model=TokenResponse)
@apply_rate_limit("30/minute")
async def dev_login(
    request: Request,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    auth_service: AuthService = Depends(get_auth_service),
    settings: Settings = Depends(get_settings),
) -> JSONResponse:
    """Sign in without Google OAuth (development only — DEBUG must be enabled)."""
    _ = request
    if settings.is_production or not settings.DEBUG:
        raise AppError("Not found", status_code=404)

    user = await auth_service.get_or_create_demo_user(db)
    token_response, refresh_token = await auth_service.create_session(redis, user)
    response = JSONResponse(content=token_response.model_dump(mode="json"))
    set_refresh_cookie(response, refresh_token, secure=settings.is_production)
    return response
