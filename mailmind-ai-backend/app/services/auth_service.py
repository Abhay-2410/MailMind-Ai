import json
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlencode
from uuid import UUID

import httpx
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.exceptions import AppError
from app.core.security import TokenError, create_access_token, create_refresh_token, decode_token
from app.models.account import Account
from app.models.user import User
from app.models.user_settings import UserSettings
from app.schemas.auth import TokenResponse, UserPublic
from app.utils.encryption import encrypt_token

OAUTH_STATE_PREFIX = "oauth_state:"
AUTH_EXCHANGE_PREFIX = "auth_exchange:"
REFRESH_SESSION_PREFIX = "refresh_session:"
OAUTH_STATE_TTL = 600
AUTH_EXCHANGE_TTL = 120


@dataclass
class GoogleUserInfo:
    google_id: str
    email: str
    full_name: str | None
    avatar_url: str | None


@dataclass
class GoogleTokenBundle:
    access_token: str
    refresh_token: str | None
    expires_in: int | None
    id_token: str | None


class AuthService:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def _ensure_google_configured(self) -> None:
        if not self.settings.GOOGLE_CLIENT_ID or not self.settings.GOOGLE_CLIENT_SECRET:
            raise AppError("Google OAuth is not configured", status_code=503)

    async def create_google_login_url(self, redis: Redis) -> tuple[str, str]:
        self._ensure_google_configured()
        state = secrets.token_urlsafe(32)
        await redis.setex(f"{OAUTH_STATE_PREFIX}{state}", OAUTH_STATE_TTL, "1")

        params = {
            "client_id": self.settings.GOOGLE_CLIENT_ID,
            "redirect_uri": self.settings.google_oauth_redirect_uri,
            "response_type": "code",
            "scope": " ".join(self.settings.google_oauth_scopes),
            "access_type": "offline",
            "include_granted_scopes": "true",
            "prompt": "consent",
            "state": state,
        }
        url = f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"
        return url, state

    async def validate_oauth_state(self, redis: Redis, state: str) -> None:
        key = f"{OAUTH_STATE_PREFIX}{state}"
        exists = await redis.get(key)
        if not exists:
            raise AppError("Invalid or expired OAuth state", status_code=400)
        await redis.delete(key)

    async def exchange_google_code(self, code: str) -> tuple[GoogleTokenBundle, GoogleUserInfo]:
        self._ensure_google_configured()

        async with httpx.AsyncClient(timeout=20.0) as client:
            token_response = await client.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "code": code,
                    "client_id": self.settings.GOOGLE_CLIENT_ID,
                    "client_secret": self.settings.GOOGLE_CLIENT_SECRET,
                    "redirect_uri": self.settings.google_oauth_redirect_uri,
                    "grant_type": "authorization_code",
                },
            )
            if token_response.status_code != 200:
                raise AppError("Failed to exchange Google authorization code", status_code=400)

            token_data = token_response.json()
            access_token = token_data.get("access_token")
            if not access_token:
                raise AppError("Google did not return an access token", status_code=400)

            userinfo_response = await client.get(
                "https://www.googleapis.com/oauth2/v2/userinfo",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            if userinfo_response.status_code != 200:
                raise AppError("Failed to fetch Google user profile", status_code=400)

            profile = userinfo_response.json()

        google_id = profile.get("id")
        email = profile.get("email")
        if not google_id or not email:
            raise AppError("Google profile is missing required fields", status_code=400)

        tokens = GoogleTokenBundle(
            access_token=access_token,
            refresh_token=token_data.get("refresh_token"),
            expires_in=token_data.get("expires_in"),
            id_token=token_data.get("id_token"),
        )
        user_info = GoogleUserInfo(
            google_id=str(google_id),
            email=email.lower(),
            full_name=profile.get("name"),
            avatar_url=profile.get("picture"),
        )
        return tokens, user_info

    async def upsert_user_from_google(
        self,
        db: AsyncSession,
        tokens: GoogleTokenBundle,
        user_info: GoogleUserInfo,
    ) -> User:
        result = await db.execute(select(User).where(User.google_id == user_info.google_id))
        user = result.scalar_one_or_none()

        if user is None:
            result = await db.execute(select(User).where(User.email == user_info.email))
            user = result.scalar_one_or_none()

        if user is None:
            user = User(
                email=user_info.email,
                full_name=user_info.full_name,
                avatar_url=user_info.avatar_url,
                google_id=user_info.google_id,
                is_active=True,
            )
            db.add(user)
            await db.flush()
            db.add(UserSettings(user_id=user.id))
        else:
            user.email = user_info.email
            user.full_name = user_info.full_name
            user.avatar_url = user_info.avatar_url
            user.google_id = user_info.google_id
            user.is_active = True

        user.last_login_at = datetime.now(UTC)

        expires_at = None
        if tokens.expires_in:
            expires_at = datetime.now(UTC) + timedelta(seconds=int(tokens.expires_in))

        account_result = await db.execute(
            select(Account).where(
                Account.user_id == user.id,
                Account.email == user_info.email,
            )
        )
        account = account_result.scalar_one_or_none()

        encrypted_access = encrypt_token(tokens.access_token, settings=self.settings)
        encrypted_refresh = (
            encrypt_token(tokens.refresh_token, settings=self.settings)
            if tokens.refresh_token
            else None
        )

        if account is None:
            account = Account(
                user_id=user.id,
                email=user_info.email,
                display_name=user_info.full_name,
                provider="google",
                access_token_encrypted=encrypted_access,
                refresh_token_encrypted=encrypted_refresh,
                token_expires_at=expires_at,
                is_primary=True,
                is_active=True,
            )
            db.add(account)
        else:
            account.display_name = user_info.full_name
            account.access_token_encrypted = encrypted_access
            if encrypted_refresh:
                account.refresh_token_encrypted = encrypted_refresh
            account.token_expires_at = expires_at
            account.is_active = True

        await db.commit()
        await db.refresh(user)
        return user

    async def get_or_create_demo_user(self, db: AsyncSession) -> User:
        """Local development user when Google OAuth is disabled."""
        demo_email = "demo@example.com"
        demo_google_id = "mailmind-demo-user"

        result = await db.execute(select(User).where(User.google_id == demo_google_id))
        user = result.scalar_one_or_none()

        if user is None:
            result = await db.execute(select(User).where(User.email == demo_email))
            user = result.scalar_one_or_none()

        if user is None:
            user = User(
                email=demo_email,
                full_name="Demo User",
                avatar_url=None,
                google_id=demo_google_id,
                is_active=True,
            )
            db.add(user)
            await db.flush()
            db.add(UserSettings(user_id=user.id))
        else:
            user.is_active = True
            user.full_name = user.full_name or "Demo User"

        user.last_login_at = datetime.now(UTC)
        await db.commit()
        await db.refresh(user)
        return user

    async def _store_refresh_session(self, redis: Redis, jti: str, user_id: str) -> None:
        ttl = self.settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60
        await redis.setex(f"{REFRESH_SESSION_PREFIX}{jti}", ttl, user_id)

    async def create_session(self, redis: Redis, user: User) -> tuple[TokenResponse, str]:
        user_id = str(user.id)
        access_token = create_access_token(user_id, settings=self.settings)
        refresh_token, jti = create_refresh_token(user_id, settings=self.settings)
        await self._store_refresh_session(redis, jti, user_id)

        token_response = TokenResponse(
            access_token=access_token,
            expires_in=self.settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            user=UserPublic.model_validate(user),
        )
        return token_response, refresh_token

    async def store_exchange_code(self, redis: Redis, token_response: TokenResponse, refresh_token: str) -> str:
        code = secrets.token_urlsafe(32)
        payload = {
            "access_token": token_response.access_token,
            "expires_in": token_response.expires_in,
            "refresh_token": refresh_token,
            "user": token_response.user.model_dump(mode="json"),
        }
        await redis.setex(
            f"{AUTH_EXCHANGE_PREFIX}{code}",
            AUTH_EXCHANGE_TTL,
            json.dumps(payload),
        )
        return code

    async def exchange_session_code(self, redis: Redis, code: str) -> tuple[TokenResponse, str]:
        key = f"{AUTH_EXCHANGE_PREFIX}{code}"
        raw = await redis.get(key)
        if not raw:
            raise AppError("Invalid or expired session code", status_code=400)
        await redis.delete(key)

        data = json.loads(raw)
        token_response = TokenResponse(
            access_token=data["access_token"],
            expires_in=data["expires_in"],
            user=UserPublic.model_validate(data["user"]),
        )
        return token_response, data["refresh_token"]

    async def refresh_session(
        self,
        redis: Redis,
        db: AsyncSession,
        refresh_token: str,
    ) -> TokenResponse:
        try:
            payload = decode_token(refresh_token, settings=self.settings, expected_type="refresh")
        except TokenError as exc:
            raise AppError("Invalid refresh token", status_code=401) from exc

        jti = payload.get("jti")
        user_id = payload.get("sub")
        if not jti or not user_id:
            raise AppError("Invalid refresh token", status_code=401)

        session_key = f"{REFRESH_SESSION_PREFIX}{jti}"
        stored_user_id = await redis.get(session_key)
        if not stored_user_id or stored_user_id != user_id:
            raise AppError("Session expired or revoked", status_code=401)

        await redis.delete(session_key)

        user = await self.get_user_by_id(db, UUID(user_id))
        if user is None or not user.is_active:
            raise AppError("User account is inactive", status_code=401)

        access_token = create_access_token(user_id, settings=self.settings)
        new_refresh_token, new_jti = create_refresh_token(user_id, settings=self.settings)
        await self._store_refresh_session(redis, new_jti, user_id)

        return TokenResponse(
            access_token=access_token,
            expires_in=self.settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            user=UserPublic.model_validate(user),
        ), new_refresh_token

    async def logout(self, redis: Redis, refresh_token: str | None) -> None:
        if not refresh_token:
            return

        try:
            payload = decode_token(refresh_token, settings=self.settings, expected_type="refresh")
        except TokenError:
            return

        jti = payload.get("jti")
        if jti:
            await redis.delete(f"{REFRESH_SESSION_PREFIX}{jti}")

    async def get_user_by_id(self, db: AsyncSession, user_id: UUID) -> User | None:
        result = await db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def get_user_from_access_token(self, db: AsyncSession, access_token: str) -> User:
        try:
            payload = decode_token(access_token, settings=self.settings, expected_type="access")
        except TokenError as exc:
            raise AppError("Invalid or expired access token", status_code=401) from exc

        user_id = payload.get("sub")
        if not user_id:
            raise AppError("Invalid access token", status_code=401)

        user = await self.get_user_by_id(db, UUID(user_id))
        if user is None:
            raise AppError("User not found", status_code=401)
        if not user.is_active:
            raise AppError("User account is inactive", status_code=403)
        return user
