import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from urllib.parse import parse_qs, urlparse

from app.core.config import get_settings
from app.models.user_settings import UserSettings
from app.services.auth_service import AuthService, GoogleTokenBundle, GoogleUserInfo


@pytest.mark.asyncio
async def test_google_login_returns_authorization_url(client: AsyncClient) -> None:
    settings = get_settings()
    response = await client.get("/api/v1/auth/google/login")
    assert response.status_code == 200
    body = response.json()
    assert "accounts.google.com" in body["authorization_url"]
    assert body["state"]
    client.mock_redis.setex.assert_called()  # type: ignore[attr-defined]

    parsed = urlparse(body["authorization_url"])
    query = parse_qs(parsed.query)
    assert query["redirect_uri"] == [settings.google_oauth_redirect_uri]


@pytest.mark.asyncio
async def test_google_oauth_config_endpoint(client: AsyncClient) -> None:
    settings = get_settings()
    response = await client.get("/api/v1/auth/google/oauth-config")
    assert response.status_code == 200
    body = response.json()
    assert body["redirect_uri"] == settings.google_oauth_redirect_uri
    assert body["backend_public_url"] == settings.BACKEND_PUBLIC_URL
    assert body["google_configured"] is True


@pytest.mark.asyncio
async def test_dev_login(client: AsyncClient) -> None:
    response = await client.post("/api/v1/auth/dev/login", json={})
    assert response.status_code == 200
    body = response.json()
    assert body["access_token"]
    assert body["user"]["email"] == "demo@example.com"


@pytest.mark.asyncio
async def test_auth_me_requires_token(client: AsyncClient) -> None:
    response = await client.get("/api/v1/auth/me")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_session_refresh_and_logout_flow(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    from datetime import UTC, datetime

    from app.models.user import User

    user = User(
        email="auth@example.com",
        full_name="Auth User",
        google_id="google-123",
        is_active=True,
        last_login_at=datetime.now(UTC),
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    auth_service = AuthService()
    token_response, refresh_token = await auth_service.create_session(client.mock_redis, user)  # type: ignore[attr-defined]

    me_response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token_response.access_token}"},
    )
    assert me_response.status_code == 200
    assert me_response.json()["email"] == "auth@example.com"

    status_response = await client.get(
        "/api/v1/auth/status",
        headers={"Authorization": f"Bearer {token_response.access_token}"},
    )
    assert status_response.status_code == 200
    assert status_response.json()["authenticated"] is True

    refresh_response = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert refresh_response.status_code == 200
    new_access = refresh_response.json()["access_token"]
    new_refresh = refresh_response.cookies.get("mailmind_refresh_token")
    assert new_access != token_response.access_token

    logout_response = await client.post(
        "/api/v1/auth/logout",
        headers={"Authorization": f"Bearer {new_access}"},
        json={"refresh_token": new_refresh or refresh_token},
    )
    assert logout_response.status_code == 200


@pytest.mark.asyncio
async def test_session_exchange(client: AsyncClient, db_session: AsyncSession) -> None:
    from datetime import UTC, datetime

    from app.models.user import User

    user = User(
        email="exchange@example.com",
        full_name="Exchange User",
        google_id="google-456",
        is_active=True,
        last_login_at=datetime.now(UTC),
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    auth_service = AuthService()
    token_response, refresh_token = await auth_service.create_session(client.mock_redis, user)  # type: ignore[attr-defined]
    exchange_code = await auth_service.store_exchange_code(
        client.mock_redis,  # type: ignore[attr-defined]
        token_response,
        refresh_token,
    )

    response = await client.post(
        "/api/v1/auth/session/exchange",
        json={"code": exchange_code},
    )
    assert response.status_code == 200
    assert response.json()["access_token"] == token_response.access_token


@pytest.mark.asyncio
async def test_upsert_user_from_google(db_session: AsyncSession) -> None:
    auth_service = AuthService()
    tokens = GoogleTokenBundle(
        access_token="google-access",
        refresh_token="google-refresh",
        expires_in=3600,
        id_token=None,
    )
    info = GoogleUserInfo(
        google_id="gid-789",
        email="newuser@gmail.com",
        full_name="New User",
        avatar_url="https://example.com/avatar.png",
    )

    user = await auth_service.upsert_user_from_google(db_session, tokens, info)
    assert user.email == "newuser@gmail.com"
    assert user.full_name == "New User"

    settings_result = await db_session.execute(
        select(UserSettings).where(UserSettings.user_id == user.id)
    )
    assert settings_result.scalar_one_or_none() is not None

    user_again = await auth_service.upsert_user_from_google(db_session, tokens, info)
    assert user_again.id == user.id
