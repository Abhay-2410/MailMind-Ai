import asyncio
import base64
import json
import logging
import re
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime
from typing import Any, ClassVar, Literal
from uuid import UUID

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.exceptions import AppError
from app.models.account import Account
from app.utils.encryption import decrypt_token, encrypt_token

logger = logging.getLogger(__name__)

GMAIL_API_BASE = "https://gmail.googleapis.com/gmail/v1/users/me"
GMAIL_BATCH_URL = "https://www.googleapis.com/batch/gmail/v1"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
METADATA_HEADERS = ["From", "Subject", "Date"]
HTTP_BATCH_SIZE = 100
BATCH_CONCURRENCY = 16
DELETE_BATCH_CONCURRENCY = 8
FALLBACK_CONCURRENCY = 48


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
    _refresh_locks: ClassVar[dict[UUID, asyncio.Lock]] = {}

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def _account_lock(self, account_id: UUID) -> asyncio.Lock:
        lock = self._refresh_locks.get(account_id)
        if lock is None:
            lock = asyncio.Lock()
            self._refresh_locks[account_id] = lock
        return lock

    @staticmethod
    def _token_is_fresh(account: Account, now: datetime) -> bool:
        expires_at = account.token_expires_at
        if expires_at is None:
            return False
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        return expires_at > now + timedelta(minutes=2)

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
            body = response.text
            logger.error(
                "Google token refresh failed (%s): %s",
                response.status_code,
                body[:500],
            )
            if "invalid_grant" in body.lower():
                raise AppError(
                    "Gmail session expired. Sign out and sign in with Google again.",
                    status_code=401,
                )
            raise AppError("Failed to refresh Gmail access token", status_code=401)
        return response.json()

    async def _persist_refreshed_token(
        self,
        account: Account,
        db: AsyncSession,
        token_data: dict[str, Any],
    ) -> str:
        access_token = token_data.get("access_token")
        if not access_token:
            raise AppError("Gmail token refresh did not return an access token", status_code=401)

        now = datetime.now(UTC)
        account.access_token_encrypted = encrypt_token(access_token, settings=self.settings)
        refreshed_scope = token_data.get("scope")
        if refreshed_scope:
            account.oauth_scopes = refreshed_scope
        expires_in = token_data.get("expires_in")
        if expires_in:
            account.token_expires_at = now + timedelta(seconds=int(expires_in))

        await db.commit()
        await db.refresh(account)
        return access_token

    async def _refresh_account_token(self, account: Account, db: AsyncSession) -> str:
        if not account.refresh_token_encrypted:
            raise AppError(
                "Gmail session expired. Sign out and sign in with Google again.",
                status_code=401,
            )

        refresh_token = decrypt_token(account.refresh_token_encrypted, settings=self.settings)
        try:
            token_data = await self.refresh_access_token(refresh_token)
        except AppError as exc:
            if "Sign out" in exc.message:
                account.refresh_token_encrypted = None
                account.token_expires_at = datetime(1970, 1, 1, tzinfo=UTC)
                await db.commit()
            raise

        return await self._persist_refreshed_token(account, db, token_data)

    def scope_includes_gmail_delete(self, scope: str | None) -> bool:
        if not scope:
            return False
        full = self.settings.gmail_full_scope
        modify = self.settings.gmail_modify_scope
        return (
            full in scope
            or "mail.google.com" in scope
            or modify in scope
            or "gmail.modify" in scope
        )

    def scope_includes_gmail_modify(self, scope: str | None) -> bool:
        return self.scope_includes_gmail_delete(scope)

    async def ensure_valid_access_token(
        self,
        account: Account,
        db: AsyncSession,
        *,
        force_refresh: bool = False,
    ) -> str:
        now = datetime.now(UTC)
        if not force_refresh and self._token_is_fresh(account, now):
            return decrypt_token(account.access_token_encrypted, settings=self.settings)

        async with self._account_lock(account.id):
            await db.refresh(account)
            if not force_refresh and self._token_is_fresh(account, now):
                return decrypt_token(account.access_token_encrypted, settings=self.settings)
            return await self._refresh_account_token(account, db)

    async def request_json(
        self,
        method: str,
        path: str,
        account: Account,
        db: AsyncSession,
        *,
        params: dict[str, Any] | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> dict[str, Any]:
        """Gmail API request with automatic token refresh on 401."""
        access_token = await self.ensure_valid_access_token(account, db)
        try:
            return await self._request(
                method,
                path,
                access_token,
                params=params,
                client=client,
            )
        except AppError as exc:
            if exc.status_code != 401:
                raise
            async with self._account_lock(account.id):
                await db.refresh(account)
                access_token = await self.ensure_valid_access_token(
                    account, db, force_refresh=True
                )
            return await self._request(
                method,
                path,
                access_token,
                params=params,
                client=client,
            )

    async def ensure_access_token_for_delete(
        self,
        account: Account,
        db: AsyncSession,
    ) -> str:
        """Obtain a fresh Gmail access token for delete operations (never use a stale cache)."""
        async with self._account_lock(account.id):
            await db.refresh(account)
            return await self._refresh_account_token(account, db)

    async def _request(
        self,
        method: str,
        path: str,
        access_token: str,
        *,
        params: dict[str, Any] | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> dict[str, Any]:
        url = f"{GMAIL_API_BASE}/{path.lstrip('/')}"
        headers = {"Authorization": f"Bearer {access_token}"}

        if client is None:
            async with httpx.AsyncClient(timeout=30.0) as owned:
                response = await owned.request(method, url, headers=headers, params=params)
        else:
            response = await client.request(method, url, headers=headers, params=params)

        if response.status_code == 401:
            raise AppError(
                "Gmail session expired. Sign out and sign in with Google again.",
                status_code=401,
            )
        if response.status_code == 403:
            raise AppError("Permission error — please re-login", status_code=403)
        if response.status_code == 429:
            raise AppError("Rate limited — wait 30s and retry", status_code=429)
        if response.status_code != 200:
            detail = self._gmail_error_detail(response)
            logger.error(
                "Gmail API %s %s failed (%s): %s",
                method,
                path,
                response.status_code,
                detail,
            )
            raise AppError(detail, status_code=502)

        return response.json()

    @staticmethod
    def _gmail_error_detail(response: httpx.Response) -> str:
        try:
            payload = response.json()
            error = payload.get("error", {})
            message = error.get("message") if isinstance(error, dict) else None
            if message:
                return str(message)
        except (json.JSONDecodeError, TypeError, ValueError):
            pass
        text = response.text.strip()
        if text:
            return text[:300]
        return "Gmail API request failed"

    @staticmethod
    def _query_needs_spam_trash(query: str | None) -> bool:
        if not query:
            return False
        lowered = query.lower()
        return "in:spam" in lowered or "is:phishing" in lowered

    async def count_query_messages(
        self,
        access_token: str | None = None,
        query: str = "",
        *,
        account: Account | None = None,
        db: AsyncSession | None = None,
    ) -> int:
        """Exact count by paginating message IDs only (never resultSizeEstimate)."""
        total = 0
        page_token: str | None = None

        async with httpx.AsyncClient(timeout=300.0) as client:
            while True:
                ids, page_token = await self.list_message_ids(
                    access_token,
                    account=account,
                    db=db,
                    query=query,
                    max_results=500,
                    page_token=page_token,
                    client=client,
                )
                total += len(ids)
                if not page_token:
                    break

        return total

    async def collect_query_message_ids(
        self,
        access_token: str | None = None,
        query: str = "",
        *,
        account: Account | None = None,
        db: AsyncSession | None = None,
    ) -> list[str]:
        all_ids: list[str] = []
        page_token: str | None = None

        async with httpx.AsyncClient(timeout=300.0) as client:
            while True:
                ids, page_token = await self.list_message_ids(
                    access_token,
                    account=account,
                    db=db,
                    query=query,
                    max_results=500,
                    page_token=page_token,
                    client=client,
                )
                all_ids.extend(ids)
                if not page_token:
                    break

        return all_ids

    async def delete_all_by_query(
        self,
        access_token: str,
        query: str,
        *,
        on_chunk_deleted: Callable[[list[str]], Awaitable[None]] | None = None,
    ) -> tuple[int, list[str]]:
        """Collect all message IDs, batchDelete in chunks of 1000, sync after each chunk."""
        all_ids = await self.collect_query_message_ids(access_token=access_token, query=query)
        if not all_ids:
            return 0, []

        url = f"{GMAIL_API_BASE}/messages/batchDelete"
        chunk_size = 1000
        deleted_ids: list[str] = []

        async with httpx.AsyncClient(timeout=300.0) as client:
            for start in range(0, len(all_ids), chunk_size):
                chunk = all_ids[start : start + chunk_size]
                response = await client.post(
                    url,
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "Content-Type": "application/json",
                    },
                    json={"ids": chunk},
                )
                if response.status_code == 403:
                    detail = self._gmail_error_detail(response)
                    logger.error("Gmail batchDelete forbidden: %s", detail)
                    raise AppError(
                        "Gmail permanent delete is not allowed with the current permissions. "
                        "Sign out, sign in with Google again, and allow full Gmail access.",
                        status_code=403,
                    )
                if response.status_code == 429:
                    raise AppError("Rate limited — wait 30s and retry", status_code=429)
                if response.status_code not in (200, 204):
                    raise AppError(
                        f"Gmail delete failed ({response.status_code})",
                        status_code=502,
                    )

                deleted_ids.extend(chunk)
                if on_chunk_deleted:
                    await on_chunk_deleted(chunk)

        return len(deleted_ids), deleted_ids

    async def list_message_ids(
        self,
        access_token: str | None = None,
        *,
        account: Account | None = None,
        db: AsyncSession | None = None,
        query: str | None = None,
        max_results: int = 50,
        page_token: str | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> tuple[list[str], str | None]:
        params: dict[str, Any] = {
            "maxResults": max_results,
        }
        if query:
            params["q"] = query
            if self._query_needs_spam_trash(query):
                params["includeSpamTrash"] = True
        if page_token:
            params["pageToken"] = page_token

        if account is not None and db is not None:
            data = await self.request_json(
                "GET",
                "messages",
                account,
                db,
                params=params,
                client=client,
            )
        elif access_token:
            data = await self._request(
                "GET", "messages", access_token, params=params, client=client
            )
        else:
            raise AppError("Gmail credentials required", status_code=401)

        messages = data.get("messages", [])
        ids = [message["id"] for message in messages if message.get("id")]
        return ids, data.get("nextPageToken")

    async def collect_message_ids(
        self,
        access_token: str,
        *,
        query: str | None = None,
        max_total: int | None = None,
        page_size: int = 500,
    ) -> list[str]:
        """List message IDs only (fast) across pages."""
        all_ids: list[str] = []
        page_token: str | None = None
        page_size = max(1, min(page_size, 500))

        async with httpx.AsyncClient(timeout=30.0) as client:
            while max_total is None or len(all_ids) < max_total:
                batch = page_size if max_total is None else min(page_size, max_total - len(all_ids))
                ids, page_token = await self.list_message_ids(
                    access_token,
                    query=query,
                    max_results=batch,
                    page_token=page_token,
                    client=client,
                )
                all_ids.extend(ids)
                if not page_token or not ids:
                    break

        return all_ids

    async def get_message(
        self,
        access_token: str | None = None,
        message_id: str = "",
        *,
        account: Account | None = None,
        db: AsyncSession | None = None,
        message_format: Literal["full", "metadata"] = "full",
        client: httpx.AsyncClient | None = None,
    ) -> GmailMessage:
        params: dict[str, Any] = {"format": message_format}
        if message_format == "metadata":
            params["metadataHeaders"] = METADATA_HEADERS

        if account is not None and db is not None:
            data = await self.request_json(
                "GET",
                f"messages/{message_id}",
                account,
                db,
                params=params,
                client=client,
            )
        elif access_token:
            data = await self._request(
                "GET",
                f"messages/{message_id}",
                access_token,
                params=params,
                client=client,
            )
        else:
            raise AppError("Gmail credentials required", status_code=401)

        return self.parse_message(data)

    def _metadata_query(self) -> str:
        params = ["format=metadata", *[f"metadataHeaders={h}" for h in METADATA_HEADERS]]
        return "&".join(params)

    def _parse_batch_response(self, raw: str) -> list[GmailMessage]:
        messages: list[GmailMessage] = []
        decoder = json.JSONDecoder()

        for block in re.split(r"HTTP/1\.1 \d+ (?:OK|Not Found)", raw):
            start = block.find("{")
            if start == -1:
                continue
            try:
                data, _ = decoder.raw_decode(block[start:])
            except json.JSONDecodeError:
                continue
            if data.get("id"):
                messages.append(self.parse_message(data))

        return messages

    async def _fetch_metadata_http_batch(
        self,
        client: httpx.AsyncClient,
        access_token: str,
        message_ids: list[str],
    ) -> list[GmailMessage]:
        boundary = f"batch_{uuid.uuid4().hex}"
        query = self._metadata_query()
        lines: list[str] = []

        for message_id in message_ids:
            lines.extend(
                [
                    f"--{boundary}",
                    "Content-Type: application/http",
                    "",
                    f"GET /gmail/v1/users/me/messages/{message_id}?{query}",
                    "",
                ]
            )
        lines.append(f"--{boundary}--")

        response = await client.post(
            GMAIL_BATCH_URL,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": f"multipart/mixed; boundary={boundary}",
            },
            content="\r\n".join(lines).encode(),
        )

        if response.status_code != 200:
            raise AppError("Gmail batch API request failed", status_code=502)

        return self._parse_batch_response(response.text)

    async def _fetch_metadata_parallel(
        self,
        client: httpx.AsyncClient,
        access_token: str,
        message_ids: list[str],
    ) -> list[GmailMessage]:
        semaphore = asyncio.Semaphore(FALLBACK_CONCURRENCY)

        async def fetch_one(message_id: str) -> GmailMessage | None:
            async with semaphore:
                try:
                    return await self.get_message(
                        access_token,
                        message_id,
                        message_format="metadata",
                        client=client,
                    )
                except AppError as exc:
                    logger.warning("Failed to fetch Gmail message %s: %s", message_id, exc)
                    return None

        results = await asyncio.gather(*(fetch_one(mid) for mid in message_ids))
        return [msg for msg in results if msg is not None]

    async def fetch_messages_batch(
        self,
        access_token: str,
        message_ids: list[str],
        *,
        message_format: Literal["full", "metadata"] = "metadata",
    ) -> list[GmailMessage]:
        """Fetch many messages via Gmail HTTP batch API (100 per request)."""
        if not message_ids:
            return []

        if message_format == "full":
            async with httpx.AsyncClient(timeout=60.0) as client:
                return await self._fetch_metadata_parallel(client, access_token, message_ids)

        chunks = [
            message_ids[i : i + HTTP_BATCH_SIZE]
            for i in range(0, len(message_ids), HTTP_BATCH_SIZE)
        ]
        semaphore = asyncio.Semaphore(BATCH_CONCURRENCY)
        messages: list[GmailMessage] = []

        async with httpx.AsyncClient(timeout=90.0) as client:
            async def fetch_chunk(chunk: list[str]) -> list[GmailMessage]:
                async with semaphore:
                    try:
                        return await self._fetch_metadata_http_batch(client, access_token, chunk)
                    except AppError as exc:
                        logger.warning("Batch fetch failed, falling back to parallel: %s", exc)
                        return await self._fetch_metadata_parallel(client, access_token, chunk)

            chunk_results = await asyncio.gather(*(fetch_chunk(chunk) for chunk in chunks))
            for chunk_messages in chunk_results:
                messages.extend(chunk_messages)

        return messages

    async def fetch_messages(
        self,
        access_token: str,
        *,
        query: str | None = None,
        max_results: int = 50,
        page_token: str | None = None,
        message_format: Literal["full", "metadata"] = "metadata",
    ) -> GmailListResult:
        ids, next_token = await self.list_message_ids(
            access_token,
            query=query,
            max_results=max_results,
            page_token=page_token,
        )
        messages = await self.fetch_messages_batch(
            access_token, ids, message_format=message_format
        )
        return GmailListResult(messages=messages, next_page_token=next_token)

    async def fetch_all_messages(
        self,
        access_token: str,
        *,
        query: str | None = None,
        max_total: int | None = None,
        page_size: int = 500,
        message_format: Literal["full", "metadata"] = "metadata",
    ) -> GmailListResult:
        """Collect IDs across pages, then fetch message data in batch."""
        ids = await self.collect_message_ids(
            access_token,
            query=query,
            max_total=max_total,
            page_size=page_size,
        )
        messages = await self.fetch_messages_batch(
            access_token, ids, message_format=message_format
        )
        return GmailListResult(messages=messages, next_page_token=None)

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

        body_text: str | None = None
        body_html: str | None = None
        if data.get("payload"):
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
