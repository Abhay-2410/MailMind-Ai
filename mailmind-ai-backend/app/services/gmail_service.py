import base64
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime
from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.exceptions import AppError
from app.models.account import Account
from app.utils.encryption import decrypt_token, encrypt_token

GMAIL_API_BASE = "https://gmail.googleapis.com/gmail/v1/users/me"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"


@dataclass
class GmailMessage:
    gmail_id: str
    thread_id: str | None
    sender: str
    sender_name: str | None
    subject: str
    preview: str | None
    body_text: str | None
    body_html: str | None
    received_at: datetime
    is_read: bool
    is_starred: bool
    is_important: bool
    labels: list[str]


@dataclass
class GmailListResult:
    messages: list[GmailMessage]
    next_page_token: str | None


class GmailService:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    async def refresh_access_token(self, refresh_token: str) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(
                GOOGLE_TOKEN_URL,
                data={
                    "client_id": self.settings.GOOGLE_CLIENT_ID,
                    "client_secret": self.settings.GOOGLE_CLIENT_SECRET,
                    "refresh_token": refresh_token,
                    "grant_type": "refresh_token",
                },
            )
        if response.status_code != 200:
            raise AppError("Failed to refresh Gmail access token", status_code=401)
        return response.json()

    async def ensure_valid_access_token(
        self,
        account: Account,
        db: AsyncSession,
    ) -> str:
        now = datetime.now(UTC)
        expires_at = account.token_expires_at
        if expires_at and expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)

        if expires_at and expires_at > now + timedelta(minutes=2):
            return decrypt_token(account.access_token_encrypted, settings=self.settings)

        if not account.refresh_token_encrypted:
            raise AppError("Gmail re-authentication required", status_code=401)

        refresh_token = decrypt_token(account.refresh_token_encrypted, settings=self.settings)
        token_data = await self.refresh_access_token(refresh_token)

        access_token = token_data.get("access_token")
        if not access_token:
            raise AppError("Gmail token refresh did not return an access token", status_code=401)

        account.access_token_encrypted = encrypt_token(access_token, settings=self.settings)
        expires_in = token_data.get("expires_in")
        if expires_in:
            account.token_expires_at = now + timedelta(seconds=int(expires_in))

        await db.commit()
        await db.refresh(account)
        return access_token

    async def _request(
        self,
        method: str,
        path: str,
        access_token: str,
        *,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        url = f"{GMAIL_API_BASE}/{path.lstrip('/')}"
        headers = {"Authorization": f"Bearer {access_token}"}

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.request(method, url, headers=headers, params=params)

        if response.status_code == 401:
            raise AppError("Gmail access token expired", status_code=401)
        if response.status_code != 200:
            raise AppError("Gmail API request failed", status_code=502)

        return response.json()

    async def list_message_ids(
        self,
        access_token: str,
        *,
        query: str | None = None,
        max_results: int = 50,
        page_token: str | None = None,
    ) -> tuple[list[str], str | None]:
        params: dict[str, Any] = {"maxResults": max_results}
        if query:
            params["q"] = query
        if page_token:
            params["pageToken"] = page_token

        data = await self._request("GET", "messages", access_token, params=params)
        messages = data.get("messages", [])
        ids = [message["id"] for message in messages if message.get("id")]
        return ids, data.get("nextPageToken")

    async def get_message(self, access_token: str, message_id: str) -> GmailMessage:
        data = await self._request(
            "GET",
            f"messages/{message_id}",
            access_token,
            params={"format": "full"},
        )
        return self.parse_message(data)

    async def fetch_messages(
        self,
        access_token: str,
        *,
        query: str | None = None,
        max_results: int = 50,
        page_token: str | None = None,
    ) -> GmailListResult:
        ids, next_token = await self.list_message_ids(
            access_token,
            query=query,
            max_results=max_results,
            page_token=page_token,
        )

        messages: list[GmailMessage] = []
        for message_id in ids:
            messages.append(await self.get_message(access_token, message_id))

        return GmailListResult(messages=messages, next_page_token=next_token)

    async def fetch_all_messages(
        self,
        access_token: str,
        *,
        query: str | None = None,
        page_size: int = 100,
        max_total: int = 2000,
    ) -> GmailListResult:
        """Fetch multiple pages of Gmail messages up to max_total."""
        all_messages: list[GmailMessage] = []
        page_token: str | None = None
        page_size = max(1, min(page_size, 500))

        while len(all_messages) < max_total:
            batch_size = min(page_size, max_total - len(all_messages))
            result = await self.fetch_messages(
                access_token,
                query=query,
                max_results=batch_size,
                page_token=page_token,
            )
            all_messages.extend(result.messages)
            page_token = result.next_page_token
            if not page_token or not result.messages:
                break

        return GmailListResult(messages=all_messages, next_page_token=page_token)

    def parse_message(self, data: dict[str, Any]) -> GmailMessage:
        label_ids = data.get("labelIds", [])
        headers = {
            header["name"].lower(): header.get("value", "")
            for header in data.get("payload", {}).get("headers", [])
        }

        sender_raw = headers.get("from", "unknown@unknown.com")
        sender_name, sender_email = self._parse_sender(sender_raw)
        subject = headers.get("subject", "(No subject)")
        received_at = self._parse_date(headers.get("date"))

        body_text, body_html = self._extract_body(data.get("payload", {}))
        preview = body_text[:500] if body_text else data.get("snippet")

        return GmailMessage(
            gmail_id=data["id"],
            thread_id=data.get("threadId"),
            sender=sender_email,
            sender_name=sender_name,
            subject=subject,
            preview=preview,
            body_text=body_text,
            body_html=body_html,
            received_at=received_at,
            is_read="UNREAD" not in label_ids,
            is_starred="STARRED" in label_ids,
            is_important="IMPORTANT" in label_ids,
            labels=label_ids,
        )

    @staticmethod
    def _parse_sender(raw: str) -> tuple[str | None, str]:
        match = re.match(r"^(?:(.*?))?\s*<?([^<>@\s]+@[^<>@\s]+)>?$", raw.strip())
        if match:
            name = (match.group(1) or "").strip().strip('"') or None
            email = match.group(2).strip().lower()
            return name, email
        return None, raw.strip().lower()

    @staticmethod
    def _parse_date(raw: str | None) -> datetime:
        if not raw:
            return datetime.now(UTC)
        try:
            parsed = parsedate_to_datetime(raw)
            if parsed.tzinfo is None:
                return parsed.replace(tzinfo=UTC)
            return parsed
        except (TypeError, ValueError, IndexError):
            return datetime.now(UTC)

    def _extract_body(self, payload: dict[str, Any]) -> tuple[str | None, str | None]:
        text_body: str | None = None
        html_body: str | None = None

        mime_type = payload.get("mimeType", "")
        body_data = payload.get("body", {}).get("data")

        if body_data:
            decoded = self._decode_base64(body_data)
            if mime_type == "text/plain":
                text_body = decoded
            elif mime_type == "text/html":
                html_body = decoded

        for part in payload.get("parts", []):
            part_text, part_html = self._extract_body(part)
            text_body = text_body or part_text
            html_body = html_body or part_html

        return text_body, html_body

    @staticmethod
    def _decode_base64(data: str) -> str:
        padded = data + "=" * (-len(data) % 4)
        return base64.urlsafe_b64decode(padded.encode()).decode("utf-8", errors="replace")
