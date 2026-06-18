import os
from collections.abc import AsyncIterator
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

os.environ.setdefault(
    "JWT_SECRET_KEY",
    "test-jwt-secret-key-for-pytest-min-32-chars",
)
os.environ.setdefault(
    "CSRF_SECRET",
    "test-csrf-secret-for-pytest-min-32-chars",
)
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://mailmind:mailmind@localhost:5432/mailmind_test",
)
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/1")
os.environ.setdefault("APP_ENV", "development")
os.environ.setdefault("DEBUG", "true")
os.environ.setdefault("GOOGLE_CLIENT_ID", "test-google-client-id")
os.environ.setdefault("GOOGLE_CLIENT_SECRET", "test-google-client-secret")
os.environ.setdefault("BACKEND_PUBLIC_URL", "http://localhost:8000")
os.environ.setdefault("FRONTEND_URL", "http://localhost:5173")

from app.core.config import get_settings
from app.core.dependencies import get_db
from app.core.redis import close_redis, get_redis, init_redis
from app.main import create_app
from app.models import Base


@pytest.fixture(scope="session")
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture(scope="session", autouse=True)
def clear_settings_cache() -> None:
    pass


@pytest.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        yield session

    await engine.dispose()


@pytest.fixture
async def client(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[AsyncClient]:
    redis_store: dict[str, str] = {}

    mock_redis = AsyncMock()

    async def _setex(key, ttl, value):
        redis_store[key] = value

    async def _get(key):
        return redis_store.get(key)

    async def _delete(key):
        redis_store.pop(key, None)
        return 1

    mock_redis.ping = AsyncMock(return_value=True)
    mock_redis.setex = AsyncMock(side_effect=_setex)
    mock_redis.get = AsyncMock(side_effect=_get)
    mock_redis.delete = AsyncMock(side_effect=_delete)

    async def _init_redis(_settings=None):
        import app.core.redis as redis_module

        redis_module._redis_client = mock_redis
        return mock_redis

    async def _override_get_db():
        yield db_session

    async def _override_get_redis():
        yield mock_redis

    monkeypatch.setattr("app.core.redis.init_redis", _init_redis)
    monkeypatch.setattr(
        "app.db.session.check_database_connection",
        AsyncMock(return_value=True),
    )

    test_app = create_app()
    test_app.dependency_overrides[get_db] = _override_get_db
    test_app.dependency_overrides[get_redis] = _override_get_redis

    import app.core.redis as redis_module

    redis_module._redis_client = mock_redis
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        ac.mock_redis = mock_redis  # type: ignore[attr-defined]
        yield ac
    await close_redis()
    test_app.dependency_overrides.clear()
