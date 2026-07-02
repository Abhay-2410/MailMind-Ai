"""Full-inbox Gmail pagination with rate-limit handling for Inbox Triage."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

import httpx

from app.core.exceptions import AppError
from app.models.account import Account
from app.services.gmail_service import GmailMessage, GmailService
from app.utils.gmail_cleanup_helpers import (
    GmailCleanupHelpers,
    ThreadInfo,
    payload_has_attachment,
    snippet_preview,
)
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

FULL_INBOX_QUERY = "in:inbox -in:chats"
MAX_RESULTS_PER_PAGE = 500
RATE_LIMIT_RETRIES = 5
RATE_LIMIT_BACKOFF_SECONDS = 2.0
FETCH_CONCURRENCY = 20


@dataclass
class TriageCandidate:
    message: GmailMessage
    thread: ThreadInfo
    has_attachment: bool
    sender_domain: str
    sender_in_contacts: bool
    user_replied_to_sender: bool


ProgressCallback = Callable[[int, int, str], Awaitable[None]]


def sender_domain(email: str) -> str:
    if "@" not in email:
        return email.lower()
    return email.rsplit("@", 1)[-1].lower()


class GmailPaginationHelpers:
    def __init__(
        self,
        gmail: GmailService | None = None,
        cleanup_helpers: GmailCleanupHelpers | None = None,
    ) -> None:
        self.gmail = gmail or GmailService()
        self.cleanup = cleanup_helpers or GmailCleanupHelpers(self.gmail)

    async def _list_page_with_retry(
        self,
        *,
        access_token: str,
        query: str,
        page_token: str | None,
        client: httpx.AsyncClient,
    ) -> tuple[list[str], str | None]:
        last_error: Exception | None = None
        for attempt in range(RATE_LIMIT_RETRIES):
            try:
                return await self.gmail.list_message_ids(
                    access_token,
                    query=query,
                    max_results=MAX_RESULTS_PER_PAGE,
                    page_token=page_token,
                    client=client,
                )
            except AppError as exc:
                if exc.status_code == 429 and attempt < RATE_LIMIT_RETRIES - 1:
                    wait = RATE_LIMIT_BACKOFF_SECONDS * (attempt + 1)
                    logger.warning("Gmail rate limited — retrying in %.1fs", wait)
                    await asyncio.sleep(wait)
                    last_error = exc
                    continue
                raise
        if last_error:
            raise last_error
        return [], None

    async def collect_full_inbox_message_ids(
        self,
        access_token: str,
        *,
        progress_callback: ProgressCallback | None = None,
    ) -> list[str]:
        """Paginate entire inbox; dedupe while preserving order."""
        seen: set[str] = set()
        ordered: list[str] = []
        page_token: str | None = None
        pages = 0

        async with httpx.AsyncClient(timeout=300.0) as client:
            while True:
                ids, page_token = await self._list_page_with_retry(
                    access_token=access_token,
                    query=FULL_INBOX_QUERY,
                    page_token=page_token,
                    client=client,
                )
                pages += 1
                for mid in ids:
                    if mid not in seen:
                        seen.add(mid)
                        ordered.append(mid)
                if progress_callback:
                    await progress_callback(len(ordered), len(ordered), "collecting_ids")
                if not page_token:
                    break

        logger.info("Collected %s inbox message IDs across %s pages", len(ordered), pages)
        return ordered

    async def collect_full_inbox_message_ids_for_account(
        self,
        account: Account,
        db: AsyncSession,
        *,
        progress_callback: ProgressCallback | None = None,
    ) -> list[str]:
        access_token = await self.gmail.ensure_valid_access_token(account, db)
        return await self.collect_full_inbox_message_ids(
            access_token,
            progress_callback=progress_callback,
        )

    async def build_triage_candidates(
        self,
        access_token: str,
        message_ids: list[str],
        user_email: str,
        *,
        progress_callback: ProgressCallback | None = None,
    ) -> list[TriageCandidate]:
        contacts = await self.cleanup.fetch_contact_emails(access_token, user_email)
        contacts_available = bool(contacts)
        total = len(message_ids)
        candidates: list[TriageCandidate] = []
        thread_cache: dict[str, ThreadInfo] = {}
        replied_senders: set[str] = set()

        async with httpx.AsyncClient(timeout=120.0) as client:
            semaphore = asyncio.Semaphore(FETCH_CONCURRENCY)

            async def fetch_one(message_id: str) -> TriageCandidate | None:
                async with semaphore:
                    try:
                        data = await self.gmail._request(
                            "GET",
                            f"messages/{message_id}",
                            access_token,
                            params={"format": "metadata", "metadataHeaders": ["From", "Subject", "Date"]},
                            client=client,
                        )
                    except AppError:
                        return None

                    message = self.gmail.parse_message(data)
                    thread_id = message.thread_id or message_id
                    if thread_id not in thread_cache:
                        thread_cache[thread_id] = await self.cleanup.get_thread_info(
                            access_token,
                            thread_id,
                            user_email=user_email,
                            client=client,
                        )
                    thread = thread_cache[thread_id]
                    if thread.has_user_reply:
                        replied_senders.add(message.sender.lower())

                    has_attachment = payload_has_attachment(data.get("payload", {}))
                    in_contacts = (
                        contacts_available
                        and bool(contacts)
                        and message.sender.lower() in contacts
                    )
                    return TriageCandidate(
                        message=message,
                        thread=thread,
                        has_attachment=has_attachment,
                        sender_domain=sender_domain(message.sender),
                        sender_in_contacts=in_contacts,
                        user_replied_to_sender=thread.has_user_reply,
                    )

            batch_size = 100
            processed = 0
            for start in range(0, total, batch_size):
                chunk = message_ids[start : start + batch_size]
                results = await asyncio.gather(*(fetch_one(mid) for mid in chunk))
                for item in results:
                    if item is not None:
                        candidates.append(item)
                processed = min(start + batch_size, total)
                if progress_callback:
                    await progress_callback(processed, total, "fetching_metadata")

        for candidate in candidates:
            if candidate.message.sender.lower() in replied_senders:
                candidate.user_replied_to_sender = True

        return candidates

    @staticmethod
    def candidate_to_ai_payload(candidate: TriageCandidate) -> dict[str, Any]:
        message = candidate.message
        return {
            "id": message.gmail_id,
            "subject": message.subject,
            "sender": message.sender,
            "sender_name": message.sender_name,
            "sender_domain": candidate.sender_domain,
            "body_snippet": snippet_preview(message.body_text or message.preview, 500),
            "thread_message_count": candidate.thread.message_count,
            "labels": message.labels,
            "is_starred": message.is_starred,
            "is_important": message.is_important,
            "received_at": message.received_at.isoformat(),
            "sender_in_contacts": candidate.sender_in_contacts,
            "user_replied_to_sender": candidate.user_replied_to_sender,
            "has_attachment": candidate.has_attachment,
        }
