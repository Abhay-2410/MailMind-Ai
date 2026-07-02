import hashlib
import hmac

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.config import get_settings
from app.utils.encryption import generate_csrf_token

CSRF_COOKIE_NAME = "mailmind_csrf"
CSRF_HEADER_NAME = "X-CSRF-Token"
CSRF_SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
CSRF_EXEMPT_PATHS = {
    "/api/v1/auth/session/exchange",
    "/api/v1/auth/dev/login",
    "/api/v1/auth/refresh",
    "/api/v1/auth/logout",
    "/api/v1/auth/google/reconnect",
    "/api/v1/inbox/sync",
    "/api/v1/cleanup",
    "/api/v1/ai/summarize",
    "/api/v1/ai/reply",
    "/api/v1/ai/categorize",
    "/api/v1/ai/search/translate",
    "/api/v1/ai/assistant",
    "/api/v1/search",
    "/api/v1/settings",
}


class CSRFMiddleware(BaseHTTPMiddleware):
    """Double-submit cookie CSRF protection for state-changing API requests."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        settings = get_settings()
        path = request.url.path

        if not path.startswith("/api/"):
            return await call_next(request)

        if request.method in CSRF_SAFE_METHODS:
            response = await call_next(request)
            if CSRF_COOKIE_NAME not in request.cookies:
                token = generate_csrf_token(settings=settings)
                response.set_cookie(
                    key=CSRF_COOKIE_NAME,
                    value=token,
                    httponly=False,
                    samesite="lax",
                    secure=settings.is_production,
                    max_age=60 * 60 * 24 * 7,
                )
            return response

        if path in CSRF_EXEMPT_PATHS or path.startswith("/api/v1/cleanup"):
            return await call_next(request)

        cookie_token = request.cookies.get(CSRF_COOKIE_NAME)
        header_token = request.headers.get(CSRF_HEADER_NAME)

        if not cookie_token or not header_token:
            return JSONResponse(
                status_code=403,
                content={"detail": "CSRF token missing"},
            )

        if not hmac.compare_digest(cookie_token, header_token):
            return JSONResponse(
                status_code=403,
                content={"detail": "CSRF token invalid"},
            )

        signature = hmac.new(
            settings.CSRF_SECRET.encode(),
            cookie_token.encode(),
            hashlib.sha256,
        ).hexdigest()

        if not hmac.compare_digest(signature, request.headers.get("X-CSRF-Signature", "")):
            # Signature header is optional in development; required in production.
            if settings.is_production:
                return JSONResponse(
                    status_code=403,
                    content={"detail": "CSRF signature invalid"},
                )

        return await call_next(request)
