from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: EmailStr
    full_name: str | None
    avatar_url: str | None
    is_active: bool
    last_login_at: datetime | None
    created_at: datetime


class GoogleLoginResponse(BaseModel):
    authorization_url: str
    state: str


class GoogleOAuthConfigResponse(BaseModel):
    redirect_uri: str
    backend_public_url: str
    frontend_callback_url: str
    google_configured: bool


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserPublic


class RefreshTokenRequest(BaseModel):
    refresh_token: str | None = None


class SessionExchangeRequest(BaseModel):
    code: str = Field(min_length=16, max_length=128)


class LogoutResponse(BaseModel):
    message: str = "Logged out successfully"


class AuthStatusResponse(BaseModel):
    authenticated: bool
    user: UserPublic | None = None
