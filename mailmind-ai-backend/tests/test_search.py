from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.account import Account
from app.models.user import User
from app.schemas.ai import TranslateSearchResponse
from app.schemas.search import SearchResponse
from app.services.email_service import EmailService
from app.services.gmail_service import GmailMessage, GmailService
from app.services.search_service import SearchService
from app.utils.encryption import encrypt_token


@pytest.mark.asyncio
async def test_search_translates_and_returns_results(db_session: AsyncSession) -> None:
    from datetime import UTC, datetime

    user = User(email="search@example.com", google_id="g-search", is_active=True)
    db_session.add(user)
    await db_session.flush()

    account = Account(
        user_id=user.id,
        email="search@example.com",
        access_token_encrypted=encrypt_token("access-token"),
        refresh_token_encrypted=encrypt_token("refresh-token"),
        token_expires_at=datetime.now(UTC),
        is_primary=True,
        is_active=True,
    )
    db_session.add(account)
    await db_session.commit()
    await db_session.refresh(user)

    gmail_message = GmailService().parse_message(
        {
            "id": "gmail-search-1",
            "threadId": "thread-1",
            "snippet": "Your Amazon order shipped",
            "labelIds": ["INBOX", "UNREAD"],
            "payload": {
                "mimeType": "text/plain",
                "headers": [
                    {"name": "From", "value": "Amazon <orders@amazon.com>"},
                    {"name": "Subject", "value": "Your order has shipped"},
                    {"name": "Date", "value": "Mon, 15 Jun 2026 10:00:00 +0000"},
                ],
                "body": {"data": "Order details"},
            },
        }
    )

    mock_ai = AsyncMock()
    mock_ai.translate_search_query = AsyncMock(
        return_value=TranslateSearchResponse(
            natural_query="Show unread Amazon emails",
            gmail_query="from:amazon is:unread",
            explanation="Unread messages from Amazon",
            model_used="deepseek/deepseek-chat",
        )
    )

    mock_gmail = AsyncMock()
    mock_gmail.ensure_valid_access_token = AsyncMock(return_value="access-token")
    mock_gmail.fetch_messages = AsyncMock(
        return_value=type("Result", (), {"messages": [gmail_message], "next_page_token": None})()
    )

    email_service = EmailService(gmail_service=mock_gmail)
    search_service = SearchService(ai_service=mock_ai, email_service=email_service)

    response = await search_service.search(
        db_session,
        user,
        query="Show unread Amazon emails",
        max_results=25,
    )

    assert response.gmail_query == "from:amazon is:unread"
    assert response.total == 1
    assert response.results[0].subject == "Your order has shipped"

    history = await search_service.list_history(db_session, user)
    assert len(history) == 1
    assert history[0].natural_query == "Show unread Amazon emails"


@pytest.mark.asyncio
async def test_search_api_requires_auth(client: AsyncClient) -> None:
    response = await client.post("/api/v1/search", json={"query": "Find internship emails"})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_search_api(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    from app.core.security import create_access_token

    user = User(email="search-api@example.com", google_id="g-search-api", is_active=True)
    db_session.add(user)
    await db_session.flush()

    account = Account(
        user_id=user.id,
        email="search-api@example.com",
        access_token_encrypted=encrypt_token("token"),
        is_primary=True,
        is_active=True,
    )
    db_session.add(account)
    await db_session.commit()
    await db_session.refresh(user)

    access_token = create_access_token(str(user.id))

    with patch.object(
        SearchService,
        "search",
        new=AsyncMock(
            return_value=SearchResponse(
                natural_query="Find internship emails",
                gmail_query="internship",
                explanation="Messages mentioning internships",
                model_used="deepseek/deepseek-chat",
                results=[],
                total=0,
            )
        ),
    ):
        response = await client.post(
            "/api/v1/search",
            json={"query": "Find internship emails"},
            headers={"Authorization": f"Bearer {access_token}"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["gmail_query"] == "internship"
    assert body["total"] == 0
