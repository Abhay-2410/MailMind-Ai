import base64
import json
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.account import Account
from app.models.user import User
from app.services.email_service import EmailService
from app.services.gmail_service import GmailMessage, GmailService
from app.utils.encryption import encrypt_token


def _sample_gmail_api_message(message_id: str = "gmail-1") -> dict:
    body = base64.urlsafe_b64encode(b"Hello from Gmail").decode()
    return {
        "id": message_id,
        "threadId": "thread-1",
        "snippet": "Hello from Gmail",
        "labelIds": ["INBOX", "UNREAD", "IMPORTANT"],
        "payload": {
            "mimeType": "text/plain",
            "headers": [
                {"name": "From", "value": "Sender <sender@example.com>"},
                {"name": "Subject", "value": "Test Subject"},
                {"name": "Date", "value": "Mon, 15 Jun 2026 10:00:00 +0000"},
            ],
            "body": {"data": body},
        },
    }


@pytest.mark.asyncio
async def test_parse_gmail_message() -> None:
    service = GmailService()
    parsed = service.parse_message(_sample_gmail_api_message())

    assert parsed.gmail_id == "gmail-1"
    assert parsed.sender == "sender@example.com"
    assert parsed.sender_name == "Sender"
    assert parsed.subject == "Test Subject"
    assert parsed.body_text == "Hello from Gmail"
    assert parsed.is_read is False
    assert parsed.is_important is True


@pytest.mark.asyncio
async def test_sync_inbox_persists_emails(db_session: AsyncSession) -> None:
    user = User(email="gmail@example.com", google_id="g-1", is_active=True)
    db_session.add(user)
    await db_session.flush()

    account = Account(
        user_id=user.id,
        email="gmail@example.com",
        access_token_encrypted=encrypt_token("access-token"),
        refresh_token_encrypted=encrypt_token("refresh-token"),
        token_expires_at=datetime.now(UTC) + timedelta(hours=1),
        is_primary=True,
        is_active=True,
    )
    db_session.add(account)
    await db_session.commit()
    await db_session.refresh(user)

    gmail_message = GmailService().parse_message(_sample_gmail_api_message())

    mock_gmail = AsyncMock()
    mock_gmail.ensure_valid_access_token = AsyncMock(return_value="access-token")
    mock_gmail.list_message_ids = AsyncMock(return_value=(["gmail-1"], None))
    mock_gmail.fetch_messages_batch = AsyncMock(return_value=[gmail_message])

    email_service = EmailService(gmail_service=mock_gmail)
    result, deferred = await email_service.sync_inbox(db_session, user, max_results=10)

    assert deferred == []

    assert result.synced_count == 1
    assert result.new_count == 1
    assert result.account_email == "gmail@example.com"

    listing = await email_service.list_emails(db_session, user)
    assert listing.total == 1
    assert listing.items[0].subject == "Test Subject"


@pytest.mark.asyncio
async def test_inbox_api_requires_auth(client: AsyncClient) -> None:
    response = await client.get("/api/v1/inbox")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_inbox_list_and_detail(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    from app.core.security import create_access_token

    user = User(email="inbox@example.com", google_id="g-2", is_active=True)
    db_session.add(user)
    await db_session.flush()

    account = Account(
        user_id=user.id,
        email="inbox@example.com",
        access_token_encrypted=encrypt_token("token"),
        is_primary=True,
        is_active=True,
    )
    db_session.add(account)
    await db_session.commit()
    await db_session.refresh(user)

    gmail_message = GmailService().parse_message(_sample_gmail_api_message("gmail-99"))
    email_service = EmailService(gmail_service=AsyncMock())
    await email_service._upsert_email(db_session, user, account, gmail_message)
    await db_session.commit()

    access_token = create_access_token(str(user.id))
    list_response = await client.get(
        "/api/v1/inbox",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert list_response.status_code == 200
    body = list_response.json()
    assert body["total"] == 1

    email_id = body["items"][0]["id"]
    detail_response = await client.get(
        f"/api/v1/emails/{email_id}",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert detail_response.status_code == 200
    assert detail_response.json()["body_text"] == "Hello from Gmail"


@pytest.mark.asyncio
async def test_get_email_returns_preview_when_gmail_fails(
    db_session: AsyncSession,
) -> None:
    from app.core.exceptions import AppError
    from app.models.email import Email

    user = User(email="preview@example.com", google_id="g-preview", is_active=True)
    db_session.add(user)
    await db_session.flush()

    account = Account(
        user_id=user.id,
        email="preview@example.com",
        access_token_encrypted=encrypt_token("token"),
        refresh_token_encrypted=encrypt_token("refresh"),
        token_expires_at=datetime.now(UTC) + timedelta(hours=1),
        is_primary=True,
        is_active=True,
    )
    db_session.add(account)
    await db_session.flush()

    email = Email(
        user_id=user.id,
        account_id=account.id,
        gmail_id="gmail-preview-1",
        sender="sender@example.com",
        subject="Preview subject",
        preview="Snippet preview text",
        received_at=datetime.now(UTC),
        is_read=True,
        is_starred=False,
        is_important=False,
    )
    db_session.add(email)
    await db_session.commit()
    await db_session.refresh(user)
    await db_session.refresh(email)

    mock_gmail = AsyncMock()
    mock_gmail.get_message = AsyncMock(
        side_effect=AppError(
            "Gmail session expired. Sign out and sign in with Google again.",
            status_code=401,
        )
    )

    email_service = EmailService(gmail_service=mock_gmail)
    detail = await email_service.get_email(db_session, user, email.id)

    assert detail.body_text == "Snippet preview text"
    assert detail.subject == "Preview subject"
