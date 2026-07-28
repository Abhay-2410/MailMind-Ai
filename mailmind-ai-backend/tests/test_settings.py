import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.account import Account
from app.models.user import User
from app.schemas.settings import ThemePreference, UpdateSettingsRequest
from app.services.settings_service import SettingsService


@pytest.mark.asyncio
async def test_get_settings_creates_defaults(db_session: AsyncSession) -> None:
    user = User(email="settings@example.com", google_id="g-set", is_active=True, full_name="Test User")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    service = SettingsService()
    settings = await service.get_settings(db_session, user)

    assert settings.email == "settings@example.com"
    assert settings.ai_model == "llama-3.1-8b-instant"
    assert settings.timezone == "UTC"
    assert settings.theme == ThemePreference.LIGHT
    assert settings.google_connected is False


@pytest.mark.asyncio
async def test_update_settings(db_session: AsyncSession) -> None:
    user = User(email="update@example.com", google_id="g-upd", is_active=True)
    db_session.add(user)
    await db_session.flush()

    db_session.add(
        Account(
            user_id=user.id,
            email="update@example.com",
            access_token_encrypted="enc",
            is_primary=True,
            is_active=True,
        )
    )
    await db_session.commit()
    await db_session.refresh(user)

    service = SettingsService()
    updated = await service.update_settings(
        db_session,
        user,
        UpdateSettingsRequest(
            full_name="Updated Name",
            display_name="Display",
            timezone="America/New_York",
            ai_model="qwen/qwen-2.5-72b-instruct",
            theme=ThemePreference.SYSTEM,
        ),
    )

    assert updated.full_name == "Updated Name"
    assert updated.display_name == "Display"
    assert updated.timezone == "America/New_York"
    assert updated.ai_model == "qwen/qwen-2.5-72b-instruct"
    assert updated.theme == ThemePreference.SYSTEM
    assert updated.google_connected is True
    assert len(updated.accounts) == 1


@pytest.mark.asyncio
async def test_update_settings_dark_theme(db_session: AsyncSession) -> None:
    user = User(email="dark@example.com", google_id="g-dark", is_active=True)
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    service = SettingsService()
    updated = await service.update_settings(
        db_session,
        user,
        UpdateSettingsRequest(theme=ThemePreference.DARK),
    )

    assert updated.theme == ThemePreference.DARK


@pytest.mark.asyncio
async def test_settings_api_requires_auth(client: AsyncClient) -> None:
    response = await client.get("/api/v1/settings")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_settings_api_get_and_patch(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    from app.core.security import create_access_token

    user = User(email="settings-api@example.com", google_id="g-set-api", is_active=True)
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    access_token = create_access_token(str(user.id))
    headers = {"Authorization": f"Bearer {access_token}"}

    get_response = await client.get("/api/v1/settings", headers=headers)
    assert get_response.status_code == 200
    assert get_response.json()["ai_model"] == "llama-3.1-8b-instant"

    patch_response = await client.patch(
        "/api/v1/settings",
        json={"display_name": "MailMind User", "timezone": "Europe/London"},
        headers=headers,
    )
    assert patch_response.status_code == 200
    body = patch_response.json()
    assert body["display_name"] == "MailMind User"
    assert body["timezone"] == "Europe/London"
