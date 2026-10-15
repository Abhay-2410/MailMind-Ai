import asyncio
import base64
import hashlib
import json
import logging
import random
import re
import time
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from email.utils import getaddresses, parsedate_to_datetime
from typing import Any, ClassVar, Literal
from uuid import UUID

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.exceptions import AppError, GmailReauthRequired
from app.models.account import Account
from app.utils.encryption import decrypt_token, encrypt_token

logger = logging.getLogger(__name__)

GMAIL_API_BASE = "https://gmail.googleapis.com/gmail/v1/users/me"
GMAIL_BATCH_URL = "https://www.googleapis.com/batch/gmail/v1"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
# Bump when METADATA_HEADERS / parse_message gain fields so stored rows get re-fetched.
SIGNALS_VERSION = 1
METADATA_HEADERS = [
    "From",
    "Subject",
    "Date",
    "To",
    "Cc",
    "List-Unsubscribe",
    "List-Id",
    "Precedence",
    "Auto-Submitted",
]
BULK_PRECEDENCE = {"bulk", "list", "junk"}
AUTOMATED_LOCAL_PART = re.compile(
    r"^(no-?reply|do-?not-?reply|notifications?|alerts?|mailer-daemon|postmaster|bounces?|automated|system)\b",
    re.IGNORECASE,
)
# Gmail enforces a per-user quota (~250 units/s; messages.get = 5 units) and recommends
# HTTP batches of <= 50 sub-requests; larger bursts come back as 403/429 rate limits.
HTTP_BATCH_SIZE = 50
BATCH_CONCURRENCY = 2
DELETE_BATCH_CONCURRENCY = 8
FALLBACK_CONCURRENCY = 10
GMAIL_MAX_RETRIES = 5
GMAIL_RETRY_BASE_SECONDS = 1.0
GMAIL_RETRY_MAX_SECONDS = 32.0
# Gmail reports per-user throttling as 403 with these reasons, not only as 429.
RATE_LIMIT_REASONS = frozenset({"ratelimitexceeded", "userratelimitexceeded"})
DAILY_QUOTA_REASONS = frozenset({"dailylimitexceeded", "quotaexceeded"})
API_DISABLED_REASONS = frozenset({"accessnotconfigured", "service_disabled"})
RATE_LIMITED_MESSAGE = "Gmail is rate limiting requests — wait a minute and retry"
PERMISSION_MESSAGE = "Gmail permission missing — sign out and sign in with Google again"
TOKEN_REJECTED_CODE = "gmail_token_rejected"
TOKEN_REFRESH_TIMEOUT_SECONDS = 20.0
# Upper bound on waiting for another request's token refresh; prevents pile-ups.
TOKEN_LOCK_TIMEOUT_SECONDS = 30.0
# Quota units per https://developers.google.com/gmail/api/reference/quota
QUOTA_RATE_UNITS_PER_SECOND = 200.0
QUOTA_BURST_UNITS = 250.0
_QUOTA_COSTS: list[tuple[str, re.Pattern[str], int]] = [
    ("POST", re.compile(r"^messages/batch(Delete|Modify)$"), 50),
    ("POST", re.compile(r"^watch$"), 100),
    ("GET", re.compile(r"^threads/[^/]+$"), 10),
    ("GET", re.compile(r"^history$"), 2),
    ("GET", re.compile(r"^(profile|labels(/[^/]+)?)$"), 1),
]
DEFAULT_QUOTA_COST = 5


def gmail_quota_cost(method: str, path: str) -> int:
    normalized = path.strip("/")
    for cost_method, pattern, cost in _QUOTA_COSTS:
        if method.upper() == cost_method and pattern.match(normalized):
            return cost
    return DEFAULT_QUOTA_COST


class GmailQuotaLimiter:
    """Per-user token bucket so sync, cleanup and triage share Gmail's per-user quota.

    In-process only: with several backend instances each gets its own bucket.
    """

    def __init__(
        self,
        rate: float = QUOTA_RATE_UNITS_PER_SECOND,
        burst: float = QUOTA_BURST_UNITS,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.rate = rate
        self.burst = burst
        self._clock = clock
        self._state: dict[str, tuple[float, float]] = {}
        self._locks: dict[str, asyncio.Lock] = {}

    @staticmethod
    def key_for_token(access_token: str) -> str:
        return hashlib.sha256(access_token.encode()).hexdigest()[:24]

    async def acquire(self, key: str, units: float) -> None:
        units = min(units, self.burst)
        lock = self._locks.setdefault(key, asyncio.Lock())
        async with lock:
            while True:
                now = self._clock()
                tokens, updated = self._state.get(key, (self.burst, now))
                tokens = min(self.burst, tokens + (now - updated) * self.rate)
                if tokens >= units:
                    self._state[key] = (tokens - units, now)
                    return
                self._state[key] = (tokens, now)
                await asyncio.sleep((units - tokens) / self.rate)


gmail_quota_limiter = GmailQuotaLimiter()


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
    recipients: list[str] = field(default_factory=list)
    list_id: str | None = None
    is_bulk: bool = False
    is_automated: bool = False


@dataclass
class GmailHistoryChanges:
    added_ids: list[str]
    deleted_ids: list[str]
    updated_ids: list[str]
    history_id: str | None
    # False when max_pages was reached before Gmail ran out of history pages.
    complete: bool = True


@dataclass
class GmailListResult:
    messages: list[GmailMessage]
    next_page_token: str | None


class GmailService:
    _refresh_locks: ClassVar[dict[UUID, asyncio.Lock]] = {}
    # Hashes of access tokens Google answered 401 for; they must not be reused until expiry.
    _rejected_tokens: ClassVar[set[str]] = set()

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def _account_lock(self, account_id: UUID) -> asyncio.Lock:
        lock = self._refresh_locks.get(account_id)
        if lock is None:
            lock = asyncio.Lock()
            self._refresh_locks[account_id] = lock
        return lock

    @classmethod
    def _mark_token_rejected(cls, access_token: str) -> None:
        if len(cls._rejected_tokens) > 1000:
            cls._rejected_tokens.clear()
        cls._rejected_tokens.add(gmail_quota_limiter.key_for_token(access_token))

    @classmethod
    def _token_was_rejected(cls, access_token: str) -> bool:
        return gmail_quota_limiter.key_for_token(access_token) in cls._rejected_tokens

    @staticmethod
    def _token_is_fresh(account: Account, now: datetime) -> bool:
        expires_at = account.token_expires_at
        if expires_at is None:
            return False
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        return expires_at > now + timedelta(minutes=2)

    async def refresh_access_token(self, refresh_token: str) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=TOKEN_REFRESH_TIMEOUT_SECONDS) as client:
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
                raise GmailReauthRequired()
            raise AppError("Failed to refresh Gmail access token — try again", status_code=502)
        return response.json()

    async def _persist_refreshed_token(
        self,
        account: Account,
        db: AsyncSession,
        token_data: dict[str, Any],
    ) -> str:
        access_token = token_data.get("access_token")
        if not access_token:
            raise AppError("Gmail token refresh did not return an access token", status_code=502)

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
            raise GmailReauthRequired()

        refresh_token = decrypt_token(account.refresh_token_encrypted, settings=self.settings)
        try:
            token_data = await self.refresh_access_token(refresh_token)
        except GmailReauthRequired:
            # Drop the dead grant so later calls fail fast instead of re-asking Google.
            account.refresh_token_encrypted = None
            account.token_expires_at = datetime(1970, 1, 1, tzinfo=UTC)
            await db.commit()
            raise

        return await self._persist_refreshed_token(account, db, token_data)

    def scope_includes_gmail_delete(self, scope: str | None) -> bool:
        """Permanent delete requires full Gmail scope (mail.google.com)."""
        if not scope:
            return False
        full = self.settings.gmail_full_scope
        return full in scope or "mail.google.com" in scope

    def scope_includes_gmail_modify(self, scope: str | None) -> bool:
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

    async def ensure_valid_access_token(
        self,
        account: Account,
        db: AsyncSession,
        *,
        force_refresh: bool = False,
        rejected_token: str | None = None,
    ) -> str:
        """Return a usable access token, refreshing it when expired or rejected.

        ``rejected_token`` lets concurrent callers that all saw the same 401 share one
        refresh: whoever gets the lock second finds a different token and reuses it.
        """
        now = datetime.now(UTC)
        if not force_refresh and self._token_is_fresh(account, now):
            current = decrypt_token(account.access_token_encrypted, settings=self.settings)
            if not self._token_was_rejected(current):
                return current

        lock = self._account_lock(account.id)
        try:
            await asyncio.wait_for(lock.acquire(), timeout=TOKEN_LOCK_TIMEOUT_SECONDS)
        except TimeoutError as exc:
            raise AppError("Gmail token refresh is taking too long — try again", status_code=503) from exc
        try:
            await db.refresh(account)
            current = decrypt_token(account.access_token_encrypted, settings=self.settings)
            replaced = rejected_token is not None and current != rejected_token
            if (
                (not force_refresh or replaced)
                and self._token_is_fresh(account, now)
                and not self._token_was_rejected(current)
            ):
                return current
            return await self._refresh_account_token(account, db)
        finally:
            lock.release()

    async def request_json(
        self,
        method: str,
        path: str,
        account: Account,
        db: AsyncSession,
        *,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
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
                json_body=json_body,
                client=client,
            )
        except AppError as exc:
            if exc.code != TOKEN_REJECTED_CODE:
                raise
        access_token = await self.ensure_valid_access_token(
            account, db, force_refresh=True, rejected_token=access_token
        )
        try:
            return await self._request(
                method,
                path,
                access_token,
                params=params,
                json_body=json_body,
                client=client,
            )
        except AppError as exc:
            if exc.code == TOKEN_REJECTED_CODE:
                raise GmailReauthRequired() from exc
            raise

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
        json_body: dict[str, Any] | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> dict[str, Any]:
        url = f"{GMAIL_API_BASE}/{path.lstrip('/')}"
        headers = {"Authorization": f"Bearer {access_token}"}
        quota_key = gmail_quota_limiter.key_for_token(access_token)
        quota_cost = gmail_quota_cost(method, path)

        async def send(http: httpx.AsyncClient) -> httpx.Response:
            for attempt in range(GMAIL_MAX_RETRIES + 1):
                await gmail_quota_limiter.acquire(quota_key, quota_cost)
                try:
                    response = await http.request(
                        method, url, headers=headers, params=params, json=json_body
                    )
                except httpx.TransportError as exc:
                    if attempt >= GMAIL_MAX_RETRIES:
                        logger.error("Gmail API %s %s unreachable: %s", method, path, exc)
                        raise AppError("Could not reach Gmail — try again", status_code=502) from exc
                    await asyncio.sleep(self._retry_delay(attempt))
                    continue
                reasons = self._error_reasons(response)
                if attempt < GMAIL_MAX_RETRIES and self._is_retryable(response.status_code, reasons):
                    delay = self._retry_delay(attempt, response.headers.get("Retry-After"))
                    logger.info(
                        "Gmail API %s %s throttled (%s %s) — retrying in %.1fs",
                        method,
                        path,
                        response.status_code,
                        ",".join(sorted(reasons)) or "-",
                        delay,
                    )
                    await asyncio.sleep(delay)
                    continue
                return response
            raise AssertionError("unreachable")

        if client is None:
            async with httpx.AsyncClient(timeout=30.0) as owned:
                response = await send(owned)
        else:
            response = await send(client)

        if response.status_code == 401:
            self._mark_token_rejected(access_token)
        self._raise_for_gmail_status(response, method=method, path=path)
        return response.json()

    @staticmethod
    def _retry_delay(attempt: int, retry_after: str | None = None) -> float:
        if retry_after:
            try:
                return min(max(float(retry_after), 0.5), GMAIL_RETRY_MAX_SECONDS)
            except ValueError:
                pass
        backoff = GMAIL_RETRY_BASE_SECONDS * (2**attempt)
        return min(backoff + random.uniform(0, 1), GMAIL_RETRY_MAX_SECONDS)

    @staticmethod
    def _reasons_from_payload(payload: Any) -> set[str]:
        error = payload.get("error") if isinstance(payload, dict) else None
        if not isinstance(error, dict):
            return set()
        reasons: set[str] = set()
        for item in (error.get("errors") or []) + (error.get("details") or []):
            if isinstance(item, dict) and item.get("reason"):
                reasons.add(str(item["reason"]).lower())
        return reasons

    @classmethod
    def _error_reasons(cls, response: httpx.Response) -> set[str]:
        if response.status_code < 400:
            return set()
        try:
            return cls._reasons_from_payload(response.json())
        except (json.JSONDecodeError, TypeError, ValueError):
            return set()

    @staticmethod
    def _is_retryable(status_code: int, reasons: set[str]) -> bool:
        if status_code == 429 or status_code >= 500:
            return True
        return status_code == 403 and bool(reasons & RATE_LIMIT_REASONS)

    def _raise_for_gmail_status(
        self,
        response: httpx.Response,
        *,
        method: str,
        path: str,
    ) -> None:
        status_code = response.status_code
        if status_code in (200, 204):
            return
        if status_code == 401:
            raise AppError(
                "Gmail rejected the access token — retry to use a refreshed token",
                status_code=502,
                code=TOKEN_REJECTED_CODE,
            )

        reasons = self._error_reasons(response)
        detail = self._gmail_error_detail(response)
        if status_code == 404:
            raise AppError(detail or "Gmail resource not found", status_code=404)

        logger.error(
            "Gmail API %s %s failed (%s, reasons=%s): %s",
            method,
            path,
            status_code,
            ",".join(sorted(reasons)) or "-",
            detail,
        )
        if status_code == 429 or reasons & RATE_LIMIT_REASONS:
            raise AppError(RATE_LIMITED_MESSAGE, status_code=429)
        if reasons & DAILY_QUOTA_REASONS:
            raise AppError("Gmail daily API quota exhausted — try again later", status_code=429)
        if reasons & API_DISABLED_REASONS:
            raise AppError(
                "Gmail API is not enabled for this Google Cloud project",
                status_code=503,
            )
        if status_code == 403:
            raise AppError(PERMISSION_MESSAGE, status_code=403)
        raise AppError(detail, status_code=502)

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

    async def get_profile(
        self,
        *,
        account: Account,
        db: AsyncSession,
        client: httpx.AsyncClient | None = None,
    ) -> dict[str, Any]:
        return await self.request_json("GET", "profile", account, db, client=client)

    async def get_history_id(self, *, account: Account, db: AsyncSession) -> str | None:
        profile = await self.get_profile(account=account, db=db)
        history_id = profile.get("historyId")
        return str(history_id) if history_id is not None else None

    async def get_syncable_message_total(self, *, account: Account, db: AsyncSession) -> int:
        """Messages a full sync should store. profile.messagesTotal already excludes
        spam and trash (it equals what messages.list returns by default)."""
        profile = await self.get_profile(account=account, db=db)
        return int(profile.get("messagesTotal") or 0)

    async def start_watch(self, *, account: Account, db: AsyncSession, topic_name: str) -> dict[str, Any]:
        """Subscribe the mailbox to Pub/Sub push notifications (expires after ~7 days)."""
        return await self.request_json(
            "POST",
            "watch",
            account,
            db,
            json_body={"topicName": topic_name, "labelFilterBehavior": "exclude", "labelIds": ["SPAM"]},
        )

    async def list_history_changes(
        self,
        *,
        account: Account,
        db: AsyncSession,
        start_history_id: str,
        max_pages: int = 200,
    ) -> GmailHistoryChanges:
        """Return mailbox changes since start_history_id (Gmail History API)."""
        added: set[str] = set()
        deleted: set[str] = set()
        updated: set[str] = set()
        page_token: str | None = None
        latest_history_id: str | None = None

        for _ in range(max_pages):
            params: dict[str, Any] = {
                "startHistoryId": start_history_id,
                "maxResults": 500,
            }
            if page_token:
                params["pageToken"] = page_token

            data = await self.request_json(
                "GET",
                "history",
                account,
                db,
                params=params,
            )
            if data.get("historyId") is not None:
                latest_history_id = str(data["historyId"])

            for entry in data.get("history", []) or []:
                for item in entry.get("messagesAdded", []) or []:
                    message = item.get("message") or {}
                    message_id = message.get("id")
                    if message_id:
                        added.add(message_id)
                        deleted.discard(message_id)
                for item in entry.get("messagesDeleted", []) or []:
                    message = item.get("message") or {}
                    message_id = message.get("id")
                    if message_id:
                        deleted.add(message_id)
                        added.discard(message_id)
                        updated.discard(message_id)
                for key in ("labelsAdded", "labelsRemoved"):
                    for item in entry.get(key, []) or []:
                        message = item.get("message") or {}
                        message_id = message.get("id")
                        if message_id and message_id not in deleted:
                            updated.add(message_id)

            page_token = data.get("nextPageToken")
            if not page_token:
                break

        updated -= added
        updated -= deleted
        return GmailHistoryChanges(
            added_ids=list(added),
            deleted_ids=list(deleted),
            updated_ids=list(updated),
            history_id=latest_history_id,
            complete=not page_token,
        )

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
                for attempt in range(GMAIL_MAX_RETRIES + 1):
                    await gmail_quota_limiter.acquire(
                        gmail_quota_limiter.key_for_token(access_token),
                        gmail_quota_cost("POST", "messages/batchDelete"),
                    )
                    response = await client.post(
                        url,
                        headers={
                            "Authorization": f"Bearer {access_token}",
                            "Content-Type": "application/json",
                        },
                        json={"ids": chunk},
                    )
                    reasons = self._error_reasons(response)
                    if attempt < GMAIL_MAX_RETRIES and self._is_retryable(
                        response.status_code, reasons
                    ):
                        await asyncio.sleep(
                            self._retry_delay(attempt, response.headers.get("Retry-After"))
                        )
                        continue
                    break
                if response.status_code == 403 and not (
                    reasons & (RATE_LIMIT_REASONS | DAILY_QUOTA_REASONS | API_DISABLED_REASONS)
                ):
                    detail = self._gmail_error_detail(response)
                    logger.error("Gmail batchDelete forbidden: %s", detail)
                    raise AppError(
                        "Gmail permanent delete is not allowed with the current permissions. "
                        "Sign out, sign in with Google again, and allow full Gmail access.",
                        status_code=403,
                    )
                self._raise_for_gmail_status(
                    response, method="POST", path="messages/batchDelete"
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

    def _parse_batch_response(
        self,
        raw: str,
        message_ids: list[str],
        boundary: str | None = None,
    ) -> tuple[list[GmailMessage], list[str]]:
        """Parse a batch response into messages plus the IDs whose sub-requests should be retried."""
        messages: list[GmailMessage] = []
        retry_ids: list[str] = []
        answered: set[int] = set()
        decoder = json.JSONDecoder()
        parts = raw.split(f"--{boundary}") if boundary else re.split(r"--batch_[^\s-]+", raw)

        for part in parts:
            status_match = re.search(r"HTTP/1\.1 (\d{3})", part)
            if not status_match:
                continue
            status_code = int(status_match.group(1))
            index_match = re.search(r"Content-ID:\s*<response-item-(\d+)>", part, re.IGNORECASE)
            index = int(index_match.group(1)) if index_match else None
            if index is not None:
                answered.add(index)

            payload: Any = None
            start = part.find("{", status_match.end())
            if start != -1:
                try:
                    payload, _ = decoder.raw_decode(part[start:])
                except json.JSONDecodeError:
                    payload = None

            if status_code == 200 and isinstance(payload, dict) and payload.get("id"):
                messages.append(self.parse_message(payload))
            elif status_code == 404:
                continue
            elif (
                index is not None
                and index < len(message_ids)
                and self._is_retryable(status_code, self._reasons_from_payload(payload))
            ):
                retry_ids.append(message_ids[index])
            else:
                logger.warning(
                    "Gmail batch item failed (%s): %s",
                    status_code,
                    self._reasons_from_payload(payload) or "-",
                )

        returned = {message.gmail_id for message in messages}
        retry_ids.extend(
            mid
            for i, mid in enumerate(message_ids)
            if i not in answered and mid not in returned and mid not in retry_ids
        )
        return messages, retry_ids

    async def _send_metadata_batch(
        self,
        client: httpx.AsyncClient,
        access_token: str,
        message_ids: list[str],
    ) -> tuple[list[GmailMessage], list[str], str | None]:
        boundary = f"batch_{uuid.uuid4().hex}"
        query = self._metadata_query()
        lines: list[str] = []

        for index, message_id in enumerate(message_ids):
            lines.extend(
                [
                    f"--{boundary}",
                    "Content-Type: application/http",
                    f"Content-ID: <item-{index}>",
                    "",
                    f"GET /gmail/v1/users/me/messages/{message_id}?{query}",
                    "",
                ]
            )
        lines.append(f"--{boundary}--")

        await gmail_quota_limiter.acquire(
            gmail_quota_limiter.key_for_token(access_token),
            DEFAULT_QUOTA_COST * len(message_ids),
        )
        try:
            response = await client.post(
                GMAIL_BATCH_URL,
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": f"multipart/mixed; boundary={boundary}",
                },
                content="\r\n".join(lines).encode(),
            )
        except httpx.TransportError as exc:
            logger.info("Gmail batch request transport error, will retry: %s", exc)
            return [], list(message_ids), None

        if response.status_code != 200:
            if self._is_retryable(response.status_code, self._error_reasons(response)):
                return [], list(message_ids), response.headers.get("Retry-After")
            raise AppError("Gmail batch API request failed", status_code=502)

        boundary_match = re.search(
            r"boundary=\"?([^\";\s]+)\"?", response.headers.get("content-type", "")
        )
        messages, retry_ids = self._parse_batch_response(
            response.text,
            message_ids,
            boundary_match.group(1) if boundary_match else None,
        )
        return messages, retry_ids, None

    async def _fetch_metadata_http_batch(
        self,
        client: httpx.AsyncClient,
        access_token: str,
        message_ids: list[str],
    ) -> list[GmailMessage]:
        messages: list[GmailMessage] = []
        pending = list(message_ids)
        for attempt in range(GMAIL_MAX_RETRIES + 1):
            fetched, pending, retry_after = await self._send_metadata_batch(
                client, access_token, pending
            )
            messages.extend(fetched)
            if not pending:
                return messages
            if attempt < GMAIL_MAX_RETRIES:
                delay = self._retry_delay(attempt, retry_after)
                logger.info(
                    "Gmail batch throttled — retrying %s messages in %.1fs",
                    len(pending),
                    delay,
                )
                await asyncio.sleep(delay)

        logger.warning("Gmail batch still throttled for %s messages; fetching individually", len(pending))
        messages.extend(await self._fetch_metadata_parallel(client, access_token, pending))
        return messages

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
        """Fetch many messages via Gmail HTTP batch API (HTTP_BATCH_SIZE per request)."""
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
        received_at = self._parse_internal_date(data.get("internalDate")) or self._parse_date(
            headers.get("date")
        )
        recipients = [
            address.strip().lower()
            for _name, address in getaddresses(
                [headers.get("to", ""), headers.get("cc", "")]
            )
            if "@" in address
        ]
        list_id = (headers.get("list-id") or "").strip()[:255] or None
        precedence = (headers.get("precedence") or "").strip().lower()
        auto_submitted = (headers.get("auto-submitted") or "").strip().lower()
        is_bulk = bool(headers.get("list-unsubscribe") or list_id or precedence in BULK_PRECEDENCE)
        is_automated = bool(auto_submitted and auto_submitted != "no") or bool(
            AUTOMATED_LOCAL_PART.match(sender_email.split("@", 1)[0])
        )

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
            recipients=recipients[:50],
            list_id=list_id,
            is_bulk=is_bulk,
            is_automated=is_automated,
        )

    @staticmethod
    def _parse_internal_date(raw: Any) -> datetime | None:
        """Gmail's internalDate (ms since epoch) — reliable, unlike the sender-controlled Date header."""
        try:
            return datetime.fromtimestamp(int(raw) / 1000, tz=UTC)
        except (TypeError, ValueError, OverflowError, OSError):
            return None

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
