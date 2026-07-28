import logging
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

BACKEND_ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = BACKEND_ROOT / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    APP_NAME: str = "MailMind AI"
    APP_ENV: Literal["development", "staging", "production"] = "development"
    DEBUG: bool = False
    API_V1_PREFIX: str = "/api/v1"

    HOST: str = "0.0.0.0"
    PORT: int = 8000
    # Public URL browsers and Google OAuth use (scheme + host + port, no path).
    BACKEND_PUBLIC_URL: str = "http://localhost:8000"

    CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"

    DATABASE_URL: str = "postgresql+asyncpg://mailmind:mailmind@localhost:5432/mailmind"
    REDIS_URL: str = "redis://localhost:6379/0"

    JWT_SECRET_KEY: str = Field(min_length=32)
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    TOKEN_ENCRYPTION_KEY: str = ""
    CSRF_SECRET: str = Field(min_length=32)

    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    # Optional override when Google Console uses a different callback than BACKEND_PUBLIC_URL.
    GOOGLE_OAUTH_REDIRECT_URI: str = ""
    FRONTEND_URL: str = "http://localhost:5173"

    OPENROUTER_API_KEY: str = ""
    # Groq — https://console.groq.com/keys (used by inbox assistant by default)
    GROQ_API_KEY: str = ""
    GROQ_ASSISTANT_MODEL: str = "llama-3.1-8b-instant"

    RATE_LIMIT_PER_MINUTE: int = 60

    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    @staticmethod
    def _normalize_database_url(url: str) -> str:
        if url.startswith("postgres://"):
            return "postgresql+asyncpg://" + url[len("postgres://") :]
        if url.startswith("postgresql://") and "+asyncpg" not in url:
            return "postgresql+asyncpg://" + url[len("postgresql://") :]
        return url

    @model_validator(mode="after")
    def normalize_runtime_urls(self) -> "Settings":
        object.__setattr__(self, "DATABASE_URL", self._normalize_database_url(self.DATABASE_URL))
        return self

    @property
    def google_oauth_scopes(self) -> list[str]:
        return [
            "openid",
            "email",
            "profile",
            # Required for messages.batchDelete (permanent delete). gmail.modify alone
            # explicitly excludes bypassing Trash / permanent deletion.
            "https://mail.google.com/",
        ]

    @property
    def gmail_full_scope(self) -> str:
        return "https://mail.google.com/"

    @property
    def gmail_modify_scope(self) -> str:
        return "https://www.googleapis.com/auth/gmail.modify"

    @property
    def google_oauth_redirect_uri(self) -> str:
        """Single source of truth for Google OAuth redirect_uri (backend callback)."""
        if self.GOOGLE_OAUTH_REDIRECT_URI.strip():
            return self.GOOGLE_OAUTH_REDIRECT_URI.strip()
        base = self.BACKEND_PUBLIC_URL.rstrip("/")
        prefix = self.API_V1_PREFIX.rstrip("/")
        return f"{base}{prefix}/auth/google/callback"

    @model_validator(mode="after")
    def validate_oauth_and_port_consistency(self) -> "Settings":
        parsed = urlparse(self.BACKEND_PUBLIC_URL)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError(
                f"BACKEND_PUBLIC_URL must be an absolute URL like http://localhost:8000, "
                f"got {self.BACKEND_PUBLIC_URL!r}"
            )

        public_port = parsed.port
        if public_port is None:
            public_port = 443 if parsed.scheme == "https" else 80

        if self.APP_ENV == "development" and public_port != self.PORT:
            logger.warning(
                "BACKEND_PUBLIC_URL port (%s) differs from PORT (%s). "
                "Google OAuth redirect_uri uses BACKEND_PUBLIC_URL: %s",
                public_port,
                self.PORT,
                self.google_oauth_redirect_uri,
            )

        return self


def get_settings() -> Settings:
    return Settings()


def log_oauth_config(settings: Settings) -> None:
    """Log OAuth redirect URI at startup (no secrets)."""
    configured = "yes" if settings.GOOGLE_CLIENT_ID and settings.GOOGLE_CLIENT_SECRET else "no"
    logger.info(
        "Google OAuth configured=%s redirect_uri=%s env_file=%s",
        configured,
        settings.google_oauth_redirect_uri,
        ENV_FILE,
    )
