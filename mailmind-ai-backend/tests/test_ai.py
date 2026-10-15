import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.provider import AICompletionResult
from app.models.account import Account
from app.models.email import Email
from app.models.user import User
from app.services.ai_service import AIService
from app.utils.ai_json import normalize_summary_payload, parse_ai_json


def test_parse_ai_json_with_markdown_fence() -> None:
    parsed = parse_ai_json(
        'Here is the summary:\n```json\n{"summary_text": "Hello", "key_points": ["a"]}\n```'
    )
    assert parsed["summary_text"] == "Hello"


def test_normalize_summary_payload_coerces_lists() -> None:
    normalized = normalize_summary_payload(
        {
            "summary": "Overview text",
            "key_points": "one\n- two",
            "priority_level": "High",
        }
    )
    assert normalized["summary_text"] == "Overview text"
    assert normalized["key_points"] == ["one", "two"]
    assert normalized["priority_level"] == "high"


@pytest.mark.asyncio
async def test_summarize_email(db_session: AsyncSession) -> None:
    user = User(email="ai@example.com", google_id="g-ai", is_active=True)
    db_session.add(user)
    await db_session.flush()

    account = Account(
        user_id=user.id,
        email="ai@example.com",
        access_token_encrypted="enc",
        is_primary=True,
        is_active=True,
    )
    db_session.add(account)
    await db_session.flush()

    email = Email(
        user_id=user.id,
        account_id=account.id,
        gmail_id="gmail-ai-1",
        sender="boss@company.com",
        subject="Quarterly Review",
        body_text="Please prepare your Q2 review by Friday.",
        received_at=datetime.now(UTC),
    )
    db_session.add(email)
    await db_session.commit()
    await db_session.refresh(user)
    await db_session.refresh(email)

    mock_result = AICompletionResult(
        content=json.dumps(
            {
                "summary_text": "Q2 review due Friday.",
                "key_points": ["Prepare Q2 review"],
                "action_items": ["Submit review by Friday"],
                "important_dates": ["Friday"],
                "priority_level": "high",
            }
        ),
        model="deepseek/deepseek-chat",
        provider="openrouter",
        prompt_tokens=100,
        completion_tokens=50,
        total_tokens=150,
    )

    mock_provider = AsyncMock()
    mock_provider.complete_json = AsyncMock(return_value=mock_result)
    mock_provider.provider_name = "openrouter"

    service = AIService()
    with patch.object(service, "_get_provider", return_value=mock_provider):
        response = await service.summarize_email(db_session, user, email.id)

    assert response.summary_text == "Q2 review due Friday."
    assert response.priority_level.value == "high"
    assert response.model_used == "openai/gpt-oss-20b"


@pytest.mark.asyncio
async def test_list_models() -> None:
    service = AIService()
    models = await service.list_models()
    assert len(models) >= 2
    assert any(model.is_default for model in models)


@pytest.mark.asyncio
async def test_ai_models_endpoint(client) -> None:
    response = await client.get("/api/v1/ai/models")
    assert response.status_code == 200
    assert len(response.json()) >= 2
