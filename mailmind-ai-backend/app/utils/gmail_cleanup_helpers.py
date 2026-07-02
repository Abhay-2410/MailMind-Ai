"""Gmail batch fetch, label filters, and delete helpers for Smart Cleanup."""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.models.account import Account
from app.schemas.cleanup import SmartCleanupCategory
from app.services.gmail_service import GMAIL_API_BASE, GmailMessage, GmailService

logger = logging.getLogger(__name__)

PEOPLE_API_BASE = "https://people.googleapis.com/v1"

CATEGORY_BASE_QUERIES: dict[SmartCleanupCategory, list[str]] = {
    SmartCleanupCategory.PRIMARY: ["category:primary -in:chats"],
    SmartCleanupCategory.PROMOTIONS: ["category:promotions"],
    SmartCleanupCategory.SOCIAL_UPDATES: ["category:social", "category:updates"],
    SmartCleanupCategory.NEWSLETTERS: ["unsubscribe"],
}

HEURISTIC_AGE_DAYS = 7
PRIMARY_AGE_DAYS = 30
DELETE_CHUNK_SIZE = 1000

GMAIL_SYSTEM_LABELS = frozenset(
    {
        "INBOX",
        "SENT",
        "DRAFT",
        "SPAM",
        "TRASH",
        "UNREAD",
        "STARRED",
        "IMPORTANT",
        "CHAT",
        "CATEGORY_PERSONAL",
        "CATEGORY_SOCIAL",
        "CATEGORY_PROMOTIONS",
        "CATEGORY_UPDATES",
        "CATEGORY_FORUMS",
    }
)


def has_user_created_label(labels: list[str]) -> bool:
    return any(label not in GMAIL_SYSTEM_LABELS for label in labels)


@dataclass
class ThreadInfo:
    thread_id: str
    message_count: int
    has_user_reply: bool


@dataclass
class CleanupCandidate:
    message: GmailMessage
    thread: ThreadInfo
    has_attachment: bool


def heuristic_gmail_query(base_query: str) -> str:
    return f"{base_query} -is:starred -is:important older_than:{HEURISTIC_AGE_DAYS}d"


def primary_gmail_query() -> str:
    return f"category:primary -in:chats -is:starred -is:important older_than:{PRIMARY_AGE_DAYS}d"


def message_is_old_enough(received_at: datetime, *, days: int) -> bool:
    cutoff = datetime.now(UTC) - timedelta(days=days)
    if received_at.tzinfo is None:
        received_at = received_at.replace(tzinfo=UTC)
    return received_at < cutoff


def payload_has_attachment(payload: dict[str, Any]) -> bool:
    if payload.get("filename"):
        return True
    body = payload.get("body", {})
    if body.get("attachmentId"):
        return True
    for part in payload.get("parts", []):
        if payload_has_attachment(part):
            return True
    return False


class GmailCleanupHelpers:
    def __init__(self, gmail: GmailService | None = None) -> None:
        self.gmail = gmail or GmailService()
        self._contacts_cache: dict[str, set[str]] = {}

    async def count_category_messages(
        self,
        account: Account,
        db: AsyncSession,
        category: SmartCleanupCategory,
    ) -> int:
        queries = CATEGORY_BASE_QUERIES[category]
        total = 0
        seen: set[str] = set()
        for base in queries:
            query = heuristic_gmail_query(base) if category != SmartCleanupCategory.PRIMARY else primary_gmail_query()
            ids = await self.gmail.collect_query_message_ids(
                query=query,
                account=account,
                db=db,
            )
            for mid in ids:
                if mid not in seen:
                    seen.add(mid)
                    total += 1
        return total

    async def collect_category_message_ids(
        self,
        account: Account,
        db: AsyncSession,
        category: SmartCleanupCategory,
    ) -> list[str]:
        seen: set[str] = set()
        ordered: list[str] = []
        for base in CATEGORY_BASE_QUERIES[category]:
            query = heuristic_gmail_query(base) if category != SmartCleanupCategory.PRIMARY else primary_gmail_query()
            ids = await self.gmail.collect_query_message_ids(
                query=query,
                account=account,
                db=db,
            )
            for mid in ids:
                if mid not in seen:
                    seen.add(mid)
                    ordered.append(mid)
        return ordered

    async def fetch_contact_emails(self, access_token: str, user_email: str) -> set[str]:
        cache_key = user_email.lower()
        if cache_key in self._contacts_cache:
            return self._contacts_cache[cache_key]

        emails: set[str] = {user_email.lower()}
        page_token: str | None = None

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                while True:
                    params: dict[str, Any] = {
                        "personFields": "emailAddresses,names",
                        "pageSize": 1000,
                    }
                    if page_token:
                        params["pageToken"] = page_token
                    response = await client.get(
                        f"{PEOPLE_API_BASE}/people/me/connections",
                        headers={"Authorization": f"Bearer {access_token}"},
                        params=params,
                    )
                    if response.status_code == 403:
                        logger.warning("People API unavailable — contact safety check skipped")
                        self._contacts_cache[cache_key] = set()
                        return set()
                    if response.status_code != 200:
                        logger.warning("People API error %s", response.status_code)
                        self._contacts_cache[cache_key] = set()
                        return set()

                    data = response.json()
                    for person in data.get("connections", []):
                        for entry in person.get("emailAddresses", []):
                            value = entry.get("value", "").strip().lower()
                            if value:
                                emails.add(value)
                    page_token = data.get("nextPageToken")
                    if not page_token:
                        break
        except httpx.RequestError as exc:
            logger.warning("People API request failed: %s", exc)
            self._contacts_cache[cache_key] = set()
            return set()

        self._contacts_cache[cache_key] = emails
        return emails

    async def get_thread_info(
        self,
        access_token: str,
        thread_id: str,
        *,
        user_email: str,
        client: httpx.AsyncClient | None = None,
    ) -> ThreadInfo:
        params = {"format": "metadata", "metadataHeaders": ["From"]}
        data = await self.gmail._request(
            "GET",
            f"threads/{thread_id}",
            access_token,
            params=params,
            client=client,
        )
        messages = data.get("messages", [])
        has_user_reply = False
        user_email_lower = user_email.lower()

        for msg in messages:
            labels = msg.get("labelIds", [])
            if "SENT" in labels or "DRAFT" in labels:
                has_user_reply = True
                break
            headers = {
                h["name"].lower(): h.get("value", "")
                for h in msg.get("payload", {}).get("headers", [])
            }
            from_raw = headers.get("from", "")
            _, sender_email = GmailService._parse_sender(from_raw)
            if sender_email == user_email_lower:
                has_user_reply = True
                break

        return ThreadInfo(
            thread_id=thread_id,
            message_count=len(messages),
            has_user_reply=has_user_reply,
        )

    async def fetch_message_with_attachment_flag(
        self,
        access_token: str,
        message_id: str,
        *,
        client: httpx.AsyncClient | None = None,
    ) -> tuple[GmailMessage, bool]:
        data = await self.gmail._request(
            "GET",
            f"messages/{message_id}",
            access_token,
            params={"format": "full"},
            client=client,
        )
        message = self.gmail.parse_message(data)
        has_attachment = payload_has_attachment(data.get("payload", {}))
        return message, has_attachment

    async def build_primary_candidates(
        self,
        access_token: str,
        message_ids: list[str],
        user_email: str,
        *,
        on_progress: asyncio.Event | None = None,
        progress_callback: Any | None = None,
    ) -> list[CleanupCandidate]:
        candidates: list[CleanupCandidate] = []
        contacts = await self.fetch_contact_emails(access_token, user_email)
        contacts_available = bool(contacts)
        total = len(message_ids)

        async with httpx.AsyncClient(timeout=60.0) as client:
            for index, message_id in enumerate(message_ids):
                message, has_attachment = await self.fetch_message_with_attachment_flag(
                    access_token, message_id, client=client
                )
                thread_id = message.thread_id or message_id
                thread = await self.get_thread_info(
                    access_token, thread_id, user_email=user_email, client=client
                )
                candidates.append(
                    CleanupCandidate(message=message, thread=thread, has_attachment=has_attachment)
                )
                if progress_callback:
                    await progress_callback(index + 1, total)
                if on_progress:
                    on_progress.set()

        return candidates

    def passes_hard_safety_rules(
        self,
        candidate: CleanupCandidate,
        *,
        contacts: set[str] | None,
        contacts_available: bool,
    ) -> tuple[bool, str]:
        message = candidate.message
        if message.is_starred or message.is_important:
            return False, "starred or important"
        if candidate.has_attachment:
            return False, "has attachment"
        if candidate.thread.message_count > 1:
            return False, "multi-message thread"
        if candidate.thread.has_user_reply:
            return False, "user replied in thread"
        if contacts_available and contacts and message.sender.lower() in contacts:
            return False, "sender in Google Contacts"
        return True, "passed"

    async def filter_heuristic_candidates(
        self,
        access_token: str,
        message_ids: list[str],
        user_email: str,
        *,
        progress_callback: Any | None = None,
    ) -> tuple[list[CleanupCandidate], list[str]]:
        """Return deletable candidates and kept reasons."""
        contacts = await self.fetch_contact_emails(access_token, user_email)
        contacts_available = bool(contacts)
        kept_ids: list[str] = []
        deletable: list[CleanupCandidate] = []
        total = len(message_ids)

        async with httpx.AsyncClient(timeout=60.0) as client:
            for index, message_id in enumerate(message_ids):
                message = await self.gmail.get_message(
                    access_token, message_id, message_format="metadata", client=client
                )
                thread_id = message.thread_id or message_id
                thread = await self.get_thread_info(
                    access_token, thread_id, user_email=user_email, client=client
                )
                _, has_attachment = await self.fetch_message_with_attachment_flag(
                    access_token, message_id, client=client
                )
                candidate = CleanupCandidate(
                    message=message, thread=thread, has_attachment=has_attachment
                )
                ok, _reason = self.passes_hard_safety_rules(
                    candidate,
                    contacts=contacts,
                    contacts_available=contacts_available,
                )
                if ok and message_is_old_enough(message.received_at, days=HEURISTIC_AGE_DAYS):
                    deletable.append(candidate)
                else:
                    kept_ids.append(message_id)
                if progress_callback:
                    await progress_callback(index + 1, total)

        return deletable, kept_ids

    async def trash_messages(
        self,
        access_token: str,
        message_ids: list[str],
    ) -> tuple[int, list[str]]:
        failed: list[str] = []
        deleted = 0

        async with httpx.AsyncClient(timeout=120.0) as client:
            semaphore = asyncio.Semaphore(20)

            async def trash_one(message_id: str) -> None:
                nonlocal deleted
                async with semaphore:
                    try:
                        await self.gmail._request(
                            "POST",
                            f"messages/{message_id}/trash",
                            access_token,
                            client=client,
                        )
                        deleted += 1
                    except AppError:
                        failed.append(message_id)

            await asyncio.gather(*(trash_one(mid) for mid in message_ids))

        return deleted, failed

    async def untrash_messages(
        self,
        access_token: str,
        message_ids: list[str],
    ) -> tuple[int, list[str]]:
        failed: list[str] = []
        restored = 0

        async with httpx.AsyncClient(timeout=120.0) as client:
            semaphore = asyncio.Semaphore(20)

            async def untrash_one(message_id: str) -> None:
                nonlocal restored
                async with semaphore:
                    try:
                        await self.gmail._request(
                            "POST",
                            f"messages/{message_id}/untrash",
                            access_token,
                            client=client,
                        )
                        restored += 1
                    except AppError:
                        failed.append(message_id)

            await asyncio.gather(*(untrash_one(mid) for mid in message_ids))

        return restored, failed

    async def permanent_delete_messages(
        self,
        access_token: str,
        message_ids: list[str],
    ) -> tuple[int, list[str]]:
        if not message_ids:
            return 0, []

        url = f"{GMAIL_API_BASE}/messages/batchDelete"
        failed: list[str] = []
        deleted = 0

        async with httpx.AsyncClient(timeout=300.0) as client:
            for start in range(0, len(message_ids), DELETE_CHUNK_SIZE):
                chunk = message_ids[start : start + DELETE_CHUNK_SIZE]
                response = await client.post(
                    url,
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "Content-Type": "application/json",
                    },
                    json={"ids": chunk},
                )
                if response.status_code in (200, 204):
                    deleted += len(chunk)
                else:
                    failed.extend(chunk)

        return deleted, failed


def snippet_preview(text: str | None, limit: int = 500) -> str:
    if not text:
        return ""
    cleaned = re.sub(r"\s+", " ", text).strip()
    return cleaned[:limit]
