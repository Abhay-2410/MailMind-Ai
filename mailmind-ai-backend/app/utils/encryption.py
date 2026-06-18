import base64
import hashlib
import secrets

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import Settings, get_settings
from app.core.exceptions import AppError


def _build_fernet(settings: Settings) -> Fernet:
    if settings.TOKEN_ENCRYPTION_KEY:
        try:
            return Fernet(settings.TOKEN_ENCRYPTION_KEY.encode())
        except Exception as exc:
            raise AppError("Invalid TOKEN_ENCRYPTION_KEY configuration", status_code=500) from exc

    if settings.is_production:
        raise AppError("TOKEN_ENCRYPTION_KEY is required in production", status_code=500)

    # Development fallback derived from JWT secret (not for production).
    digest = hashlib.sha256(settings.JWT_SECRET_KEY.encode()).digest()
    key = base64.urlsafe_b64encode(digest)
    return Fernet(key)


def encrypt_token(plaintext: str, *, settings: Settings | None = None) -> str:
    fernet = _build_fernet(settings or get_settings())
    return fernet.encrypt(plaintext.encode()).decode()


def decrypt_token(ciphertext: str, *, settings: Settings | None = None) -> str:
    fernet = _build_fernet(settings or get_settings())
    try:
        return fernet.decrypt(ciphertext.encode()).decode()
    except InvalidToken as exc:
        raise AppError("Unable to decrypt stored token", status_code=500) from exc


def generate_csrf_token(*, settings: Settings | None = None) -> str:
    settings = settings or get_settings()
    return secrets.token_urlsafe(32)
