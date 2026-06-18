from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.provider import AICompletionResult
from app.models.account import Account
from app.models.email import Email
from app.models.user import User
from app.services.assistant_service import AssistantService


@pytest.mark.asyncio
async def test_assistant_ask(db_session: AsyncSession) -> None:
    from datetime import UTC, datetime

    user = User(email="assist@example.com", google_id="g-asst", is_active=True)
    db_session.add(user)
    await db_session.flush()

    account = Account(
        user_id=user.id,
        email="assist@example.com",
        access_token_encrypted="enc",
        is_primary=True,
        is_active=True,
    )
    db_session.add(account)
    await db_session.flush()

    db_session.add(
        Email(
            user_id=user.id,
            account_id=account.id,
            gmail_id="g1",
            sender="boss@company.com",
            subject="Project deadline Friday",
            preview="Please submit the report by Friday.",
            received_at=datetime.now(UTC),
            is_read=False,
        )
    )
    await db_session.commit()
    await db_session.refresh(user)

    mock_result = AICompletionResult(
        content="You have one unread email about a project deadline on Friday.",
        model="deepseek/deepseek-chat",
        provider="openrouter",
        prompt_tokens=100,
        completion_tokens=40,
        total_tokens=140,
    )

    mock_provider = AsyncMock()
    mock_provider.complete = AsyncMock(return_value=mock_result)
    mock_provider.provider_name = "openrouter"

    service = AssistantService()
    with patch.object(service, "_get_provider", return_value=mock_provider):
        response = await service.ask(db_session, user, "What deadlines do I have?")

    assert "Friday" in response.answer
    assert response.model_used == "deepseek/deepseek-chat"


@pytest.mark.asyncio
async def test_assistant_api_requires_auth(client: AsyncClient) -> None:
    response = await client.post("/api/v1/ai/assistant", json={"question": "Summarize unread emails"})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_assistant_api(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    from app.core.security import create_access_token

    user = User(email="assist-api@example.com", google_id="g-asst-api", is_active=True)
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    access_token = create_access_token(str(user.id))

    mock_provider = AsyncMock()
    mock_provider.complete = AsyncMock(
        return_value=AICompletionResult(
            content="No emails synced yet.",
            model="deepseek/deepseek-chat",
            provider="openrouter",
            prompt_tokens=50,
            completion_tokens=20,
            total_tokens=70,
        )
    )

    with patch("app.services.ai_service.get_provider", return_value=mock_provider):
        response = await client.post(
            "/api/v1/ai/assistant",
            json={"question": "Summarize my inbox"},
            headers={"Authorization": f"Bearer {access_token}"},
        )

    assert response.status_code == 200
    body = response.json()
    assert "answer" in body
    assert body["model_used"] == "deepseek/deepseek-chat"
