import re
from typing import Any

from pydantic import EmailStr, TypeAdapter, ValidationError

from app.core.exceptions import AppError

_EMAIL_ADAPTER = TypeAdapter(EmailStr)

SAFE_STRING_PATTERN = re.compile(r"^[\w\s@.\-+',!?():;/#&]+$")
GMAIL_QUERY_PATTERN = re.compile(r"^[\w\s@.\-+':\"/()\[\]{}]+$")


def validate_email(value: str) -> str:
    try:
        return str(_EMAIL_ADAPTER.validate_python(value.strip().lower()))
    except ValidationError as exc:
        raise AppError("Invalid email address") from exc


def sanitize_string(value: str, *, max_length: int = 500) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise AppError("Value cannot be empty")
    if len(cleaned) > max_length:
        raise AppError(f"Value exceeds maximum length of {max_length}")
    if not SAFE_STRING_PATTERN.match(cleaned):
        raise AppError("Value contains unsupported characters")
    return cleaned


def sanitize_gmail_query(value: str, *, max_length: int = 1000) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise AppError("Search query cannot be empty")
    if len(cleaned) > max_length:
        raise AppError(f"Search query exceeds maximum length of {max_length}")
    if not GMAIL_QUERY_PATTERN.match(cleaned):
        raise AppError("Search query contains unsupported characters")
    return cleaned


def clamp_pagination(page: int, page_size: int, *, max_page_size: int = 100) -> tuple[int, int]:
    if page < 1:
        raise AppError("Page must be >= 1")
    if page_size < 1 or page_size > max_page_size:
        raise AppError(f"Page size must be between 1 and {max_page_size}")
    return page, page_size


def strip_null_bytes(data: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value.replace("\x00", "") if isinstance(value, str) else value
        for key, value in data.items()
    }
