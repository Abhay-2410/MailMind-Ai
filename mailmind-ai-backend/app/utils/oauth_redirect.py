import re
from urllib.parse import urlparse

_DEV_ORIGIN = re.compile(
    r"^https?://("
    r"localhost"
    r"|127\.0\.0\.1"
    r"|192\.168\.\d{1,3}\.\d{1,3}"
    r"|10\.\d{1,3}\.\d{1,3}\.\d{1,3}"
    r")(:\d+)?$",
    re.IGNORECASE,
)


def normalize_origin(origin: str) -> str:
    parsed = urlparse(origin.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError(f"Invalid origin: {origin!r}")
    return f"{parsed.scheme}://{parsed.netloc}".rstrip("/")


def is_allowed_dev_origin(origin: str) -> bool:
    try:
        normalized = normalize_origin(origin)
    except ValueError:
        return False
    return _DEV_ORIGIN.match(normalized) is not None


def build_oauth_redirect_uri(origin: str, *, api_prefix: str = "/api/v1") -> str:
    base = normalize_origin(origin)
    prefix = api_prefix.rstrip("/")
    return f"{base}{prefix}/auth/google/callback"


def list_dev_redirect_uris(*, frontend_port: int = 5173, backend_port: int = 8000) -> list[str]:
    bases = [
        f"http://localhost:{frontend_port}",
        f"http://127.0.0.1:{frontend_port}",
        f"http://localhost:{backend_port}",
        f"http://127.0.0.1:{backend_port}",
    ]
    return [build_oauth_redirect_uri(base) for base in bases]


def list_dev_authorized_origins(*, frontend_port: int = 5173) -> list[str]:
    return [
        f"http://localhost:{frontend_port}",
        f"http://127.0.0.1:{frontend_port}",
    ]
