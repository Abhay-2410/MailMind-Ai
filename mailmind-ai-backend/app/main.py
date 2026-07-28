from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.api.router import api_router
from app.core.config import get_settings, log_oauth_config
from app.core.exceptions import register_exception_handlers
from app.core.redis import close_redis, init_redis
from app.middleware.csrf import CSRFMiddleware
from app.middleware.rate_limit import limiter


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    log_oauth_config(settings)
    await init_redis(settings)
    yield
    await close_redis()


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title=settings.APP_NAME,
        version="0.1.0",
        description="AI-powered Gmail copilot API",
        debug=settings.DEBUG,
        lifespan=lifespan,
        docs_url="/docs" if not settings.is_production else None,
        redoc_url="/redoc" if not settings.is_production else None,
    )

    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    register_exception_handlers(app)

    app.add_middleware(SlowAPIMiddleware)
    app.add_middleware(CSRFMiddleware)
    cors_kwargs: dict = {
        "allow_origins": settings.cors_origins,
        "allow_credentials": True,
        "allow_methods": ["*"],
        "allow_headers": ["*"],
        "expose_headers": ["X-CSRF-Token"],
    }
    if not settings.is_production:
        from app.utils.oauth_redirect import DEV_CORS_ORIGIN_REGEX

        # Phone / LAN SPA origins (172.x, 192.168.x, 10.x) beyond CORS_ORIGINS.
        cors_kwargs["allow_origin_regex"] = DEV_CORS_ORIGIN_REGEX

    app.add_middleware(CORSMiddleware, **cors_kwargs)

    @app.get("/", tags=["root"])
    async def root() -> dict[str, str]:
        return {
            "service": settings.APP_NAME,
            "docs": "/docs",
            "health": f"{settings.API_V1_PREFIX}/health",
        }

    app.include_router(api_router)

    return app


app = create_app()
