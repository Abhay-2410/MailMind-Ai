import logging
from pathlib import Path
from typing import Literal
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

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
    # Logs every SQL statement with parameters (includes email contents) — keep off unless debugging queries.
    SQL_ECHO: bool = False
    API_V1_PREFIX: str = "/api/v1"

    HOST: str = "0.0.0.0"
    PORT: int = 8000
    # Public URL browsers and Google OAuth use (scheme + host + port, no path).
    BACKEND_PUBLIC_URL: str = "http://localhost:8000"

    CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"

    DATABASE_URL: str = "postgresql+asyncpg://mailmind:mailmind@localhost:5432/mailmind"
    # Direct (non-PgBouncer) URL from Neon; preferred because asyncpg prepared statements
    # break behind transaction-mode poolers.
    DATABASE_URL_UNPOOLED: str = ""
    REDIS_URL: str = "redis://localhost:6379/0"

    # Set to "1" by the Vercel runtime. Serverless mode has no long-lived process, so
    # background loops are replaced by client-driven sync steps and a cron endpoint.
    VERCEL: str = ""
    # Vercel Cron sends "Authorization: Bearer $CRON_SECRET".
    CRON_SECRET: str = ""

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
    GROQ_ASSISTANT_MODEL: str = "openai/gpt-oss-20b"
    # Larger Groq model retried for low-confidence categorizations (empty disables escalation).
    AI_ESCALATION_MODEL: str = "openai/gpt-oss-120b"

    # Server-side incremental Gmail sync interval; 0 disables (then only open browser tabs sync).
    BACKGROUND_SYNC_INTERVAL_SECONDS: int = 30

    # Gmail push notifications (users.watch -> Pub/Sub push subscription -> /api/v1/gmail/push).
    # Leave GMAIL_PUBSUB_TOPIC empty to disable; polling sync keeps working either way.
    GMAIL_PUBSUB_TOPIC: str = ""
    GMAIL_PUSH_AUDIENCE: str = ""
    GMAIL_PUSH_SERVICE_ACCOUNT: str = ""

    RATE_LIMIT_PER_MINUTE: int = 60

    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"

    @property
    def is_serverless(self) -> bool:
        return self.VERCEL.strip() == "1"

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    @staticmethod
    def _normalize_database_url(url: str) -> str:
        if url.startswith("postgres://"):
            url = "postgresql+asyncpg://" + url[len("postgres://") :]
        elif url.startswith("postgresql://") and "+asyncpg" not in url:
            url = "postgresql+asyncpg://" + url[len("postgresql://") :]
        parsed = urlparse(url)
        if not parsed.query:
            return url
        # libpq-style params (Neon/Vercel URLs) are not asyncpg connect() kwargs.
        params = dict(parse_qsl(parsed.query, keep_blank_values=True))
        sslmode = params.pop("sslmode", None)
        params.pop("channel_binding", None)
        if sslmode and sslmode != "disable" and "ssl" not in params:
            params["ssl"] = "require"
        return urlunparse(parsed._replace(query=urlencode(params)))

    @model_validator(mode="after")
    def normalize_runtime_urls(self) -> "Settings":
        url = self.DATABASE_URL_UNPOOLED.strip() or self.DATABASE_URL
        object.__setattr__(self, "DATABASE_URL", self._normalize_database_url(url))
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
