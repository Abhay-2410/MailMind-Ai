import re
from urllib.parse import urlparse

# Localhost + RFC1918 private ranges (incl. 172.16.0.0/12 used by hotspots/WSL).
_DEV_ORIGIN = re.compile(
    r"^https?://("
    r"localhost"
    r"|127\.0\.0\.1"
    r"|192\.168\.\d{1,3}\.\d{1,3}"
    r"|10\.\d{1,3}\.\d{1,3}\.\d{1,3}"
    r"|172\.(1[6-9]|2\d|3[0-1])\.\d{1,3}\.\d{1,3}"
    r")(:\d+)?$",
    re.IGNORECASE,
)

_PRIVATE_HOST = re.compile(
    r"^("
    r"192\.168\.\d{1,3}\.\d{1,3}"
    r"|10\.\d{1,3}\.\d{1,3}\.\d{1,3}"
    r"|172\.(1[6-9]|2\d|3[0-1])\.\d{1,3}\.\d{1,3}"
    r")$",
    re.IGNORECASE,
)

# FastAPI CORSMiddleware allow_origin_regex (development only).
DEV_CORS_ORIGIN_REGEX = (
    r"^https?://("
    r"localhost"
    r"|127\.0\.0\.1"
    r"|192\.168\.\d{1,3}\.\d{1,3}"
    r"|10\.\d{1,3}\.\d{1,3}\.\d{1,3}"
    r"|172\.(1[6-9]|2\d|3[0-1])\.\d{1,3}\.\d{1,3}"
    r")(:\d+)?$"
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


def is_private_lan_origin(origin: str) -> bool:
    """True for RFC1918 hosts (phone/LAN), false for localhost/127.0.0.1."""
    try:
        host = urlparse(normalize_origin(origin)).hostname or ""
    except ValueError:
        return False
    return bool(_PRIVATE_HOST.match(host))


def build_oauth_redirect_uri(origin: str, *, api_prefix: str = "/api/v1") -> str:
    base = normalize_origin(origin)
    prefix = api_prefix.rstrip("/")
    return f"{base}{prefix}/auth/google/callback"


def resolve_dev_oauth_redirect_uri(
    *,
    origin: str | None,
    backend_redirect_uri: str,
    api_prefix: str = "/api/v1",
) -> str:
    """Pick a Google redirect_uri the browser can actually reach.

    Desktop (localhost) keeps the stable backend URI.
    Phone/LAN browsers cannot open the PC's localhost, so the callback must
    hit the same LAN host the SPA is on (Vite proxies /api → backend).
    """
    if origin and is_allowed_dev_origin(origin) and is_private_lan_origin(origin):
        return build_oauth_redirect_uri(origin, api_prefix=api_prefix)
    return backend_redirect_uri


def list_dev_redirect_uris(*, frontend_port: int = 5173, backend_port: int = 8000) -> list[str]:
    """Stable Google Console redirect URIs (backend public URL only)."""
    _ = frontend_port
    bases = [
        f"http://localhost:{backend_port}",
        f"http://127.0.0.1:{backend_port}",
    ]
    return [build_oauth_redirect_uri(base) for base in bases]


def list_dev_authorized_origins(*, frontend_port: int = 5173) -> list[str]:
    return [
        f"http://localhost:{frontend_port}",
        f"http://127.0.0.1:{frontend_port}",
    ]
