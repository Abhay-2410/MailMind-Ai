import asyncio
import json
import logging
import time
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.background import spawn
from app.core.exceptions import AppError, GmailReauthRequired
from app.models.account import Account
from app.models.category import Category, EmailCategory
from app.models.email import Email
from app.models.summary import Summary
from app.models.user import User
from app.schemas.email import (
    EmailDetail,
    EmailListItem,
    EmailListResponse,
    EmailSortField,
    SortOrder,
    SyncInboxResponse,
)
from app.services.categorization_service import CategorizationService
from app.services.classifier import PRIORITY_THRESHOLD
from app.services.gmail_push_service import ensure_gmail_watch
from app.services.gmail_service import SIGNALS_VERSION, GmailHistoryChanges, GmailMessage, GmailService
from app.utils.validators import clamp_pagination, sanitize_gmail_query, sanitize_string

logger = logging.getLogger(__name__)

FAST_SYNC_BATCH = 500
GMAIL_LIST_PAGE_SIZE = 500
# Inbox first for fast UI, then everything else (archive, sent, drafts). Disjoint on purpose.
SYNC_PHASE_QUERIES = ("in:inbox", "-in:inbox")
AI_CATEGORIZE_AFTER_FULL_SYNC = 300
AI_CATEGORIZE_AFTER_INCREMENTAL = 30
EXCLUDED_LABELS = frozenset({"TRASH", "SPAM"})
# Deletion reconciliation is skipped when a listing looks suspiciously short.
RECONCILE_MIN_DB_ROWS = 200
RECONCILE_MIN_LISTED_SHARE = 0.5
FALLBACK_WINDOW = timedelta(days=1)
FALLBACK_WINDOW_FIRST_SYNC = timedelta(days=7)
# Hard cap so a hung Gmail call can never wedge the per-user incremental lock.
INCREMENTAL_SYNC_TIMEOUT_SECONDS = 180

_categorize_locks: dict[str, asyncio.Lock] = {}
_incremental_locks: dict[str, asyncio.Lock] = {}
_incremental_pending: set[str] = set()


class _SyncDeadlineReached(Exception):
    pass


async def run_full_inbox_sync_job(
    user_id: UUID,
    *,
    deadline: float | None = None,
    categorize_after: bool = True,
) -> str:
    """Paginated full Gmail sync: inbox first, then the rest; re-fetches stale rows and
    removes rows that no longer exist in Gmail.

    With a ``deadline`` (time.monotonic()), stops between batches and returns "paused"
    leaving the job running; calling again resumes cheaply because stored messages are
    skipped. Returns "completed", "paused" or "failed".
    """
    from app.db.session import AsyncSessionLocal
    from app.services.sync_jobs import inbox_sync_job_store

    job = await inbox_sync_job_store.load(user_id) or inbox_sync_job_store.get_or_create(user_id)
    started_at = datetime.now(UTC)
    # Listing restarts each run; download counters carry over from a paused run.
    prior_listed = job.listed_count
    counters = {
        "listed": 0,
        "fetched": job.fetched_count,
        "new": job.new_count,
        "updated": job.updated_count,
    }

    def listed() -> int:
        return max(prior_listed, counters["listed"])

    def check_deadline() -> None:
        if deadline is not None and time.monotonic() >= deadline:
            raise _SyncDeadlineReached

    try:
        async with AsyncSessionLocal() as db:
            service = EmailService()
            result = await db.execute(select(User).where(User.id == user_id))
            user = result.scalar_one_or_none()
            if user is None:
                await inbox_sync_job_store.fail(job, "User not found")
                return "failed"

            account = await service.get_primary_account(db, user.id)
            existing_ids = await service._existing_gmail_ids(db, account.id)
            stale_ids = await service._stale_gmail_ids(db, account.id)
            # Don't sit "idle in transaction" on a pooled connection while Gmail pages load.
            await db.commit()
            seen_ids: set[str] = set()
            # Captured before listing so changes made during the sync are replayed by history.
            try:
                start_history_id = await service.gmail.get_history_id(account=account, db=db)
            except GmailReauthRequired:
                raise
            except AppError as exc:
                logger.warning("Could not read Gmail historyId before full sync: %s", exc)
                start_history_id = None

            for phase_query in SYNC_PHASE_QUERIES:
                page_token: str | None = None
                while True:
                    check_deadline()
                    ids, page_token = await service.gmail.list_message_ids(
                        account=account,
                        db=db,
                        query=phase_query,
                        max_results=GMAIL_LIST_PAGE_SIZE,
                        page_token=page_token,
                    )
                    counters["listed"] += len(ids)
                    seen_ids.update(ids)
                    ids_to_fetch = [gid for gid in ids if gid not in existing_ids or gid in stale_ids]

                    for start in range(0, len(ids_to_fetch), FAST_SYNC_BATCH):
                        check_deadline()
                        chunk = ids_to_fetch[start : start + FAST_SYNC_BATCH]
                        access_token = await service.gmail.ensure_valid_access_token(account, db)
                        messages = await service.gmail.fetch_messages_batch(access_token, chunk)
                        _emails, new_count, updated_count = await service._bulk_upsert_emails(
                            db, user, account, messages
                        )
                        counters["fetched"] += len(messages)
                        counters["new"] += new_count
                        counters["updated"] += updated_count
                        fetched = {message.gmail_id for message in messages}
                        existing_ids.update(fetched)
                        stale_ids.difference_update(fetched)
                        await db.commit()
                        await inbox_sync_job_store.update(
                            job,
                            listed_count=listed(),
                            fetched_count=counters["fetched"],
                            new_count=counters["new"],
                            updated_count=counters["updated"],
                        )

                    await inbox_sync_job_store.update(job, listed_count=listed())
                    if not page_token:
                        break

            removed = await service._reconcile_deleted(
                db, account.id, seen_ids, created_before=started_at
            )
            counters["updated"] += removed
            if start_history_id:
                account.gmail_history_id = start_history_id
            account.last_synced_at = datetime.now(UTC)
            await db.commit()
            await ensure_gmail_watch(db, account, service.gmail)

            await inbox_sync_job_store.update(
                job, phase="categorizing", updated_count=counters["updated"]
            )
            stats = await CategorizationService().recategorize_user(db, user, use_ai=False)

        await inbox_sync_job_store.complete(job)
        logger.info(
            "Full inbox sync completed for user %s: listed=%s fetched=%s new=%s removed=%s categorized=%s",
            user_id,
            counters["listed"],
            counters["fetched"],
            counters["new"],
            removed,
            stats,
        )
    except _SyncDeadlineReached:
        await inbox_sync_job_store.update(
            job,
            listed_count=listed(),
            fetched_count=counters["fetched"],
            new_count=counters["new"],
            updated_count=counters["updated"],
        )
        logger.info("Full inbox sync for user %s paused at the time budget; will resume", user_id)
        return "paused"
    except Exception as exc:  # noqa: BLE001
        logger.warning("Full inbox sync failed for user %s: %r", user_id, exc)
        message = exc.message if isinstance(exc, AppError) else "Sync failed — it will retry automatically"
        await inbox_sync_job_store.fail(job, message)
        return "failed"

    if categorize_after:
        await categorize_recent_emails_job(user_id, AI_CATEGORIZE_AFTER_FULL_SYNC)
    return "completed"


def incremental_sync_lock(user_id: UUID) -> asyncio.Lock:
    """Serializes incremental syncs per user (API polling, background loop, push) so two
    syncs never insert the same Gmail message concurrently."""
    return _incremental_locks.setdefault(str(user_id), asyncio.Lock())


async def run_incremental_sync_job(user_id: UUID) -> bool:
    """History-based sync used by the background loop and Gmail push. Calls that arrive
    while a sync is running coalesce into one rerun. Returns False on failure."""
    from app.db.session import AsyncSessionLocal

    key = str(user_id)
    lock = incremental_sync_lock(user_id)
    if lock.locked():
        _incremental_pending.add(key)
        return True

    async with lock:
        while True:
            _incremental_pending.discard(key)
            try:
                async with asyncio.timeout(INCREMENTAL_SYNC_TIMEOUT_SECONDS), AsyncSessionLocal() as db:
                    result = await db.execute(select(User).where(User.id == user_id))
                    user = result.scalar_one_or_none()
                    if user is None:
                        return True
                    response, _ = await EmailService().sync_inbox(db, user, incremental=True)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Background incremental sync failed for user %s: %s", user_id, exc)
                return False
            if response.new_count:
                logger.info("Background sync stored %s new email(s) for user %s", response.new_count, user_id)
                spawn(categorize_recent_emails_job(user_id, AI_CATEGORIZE_AFTER_INCREMENTAL))
            if key not in _incremental_pending:
                return True


async def sync_remaining_emails_job(user_id: UUID, gmail_ids: list[str]) -> None:
    """Background job: fetch and persist remaining Gmail messages after a fast sync response."""
    if not gmail_ids:
        return

    from app.db.session import AsyncSessionLocal

    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(User).where(User.id == user_id))
            user = result.scalar_one_or_none()
            if user is None:
                return

            service = EmailService()
            account = await service.get_primary_account(db, user.id)
            access_token = await service.gmail.ensure_valid_access_token(account, db)
            messages = await service.gmail.fetch_messages_batch(access_token, gmail_ids)
            await service._bulk_upsert_emails(db, user, account, messages)
            account.last_synced_at = datetime.now(UTC)
            await db.commit()
            logger.info(
                "Background sync stored %s emails for user %s",
                len(messages),
                user_id,
            )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Background email sync job failed: %s", exc)


async def categorize_recent_emails_job(user_id: UUID, ai_limit: int = AI_CATEGORIZE_AFTER_INCREMENTAL) -> None:
    """Background job: full deterministic pass, then AI for the most recent uncertain emails."""
    from app.db.session import AsyncSessionLocal

    lock = _categorize_locks.setdefault(str(user_id), asyncio.Lock())
    if lock.locked():
        return

    async with lock:
        try:
            async with AsyncSessionLocal() as db:
                result = await db.execute(select(User).where(User.id == user_id))
                user = result.scalar_one_or_none()
                if user is None:
                    return
                stats = await CategorizationService().recategorize_user(db, user, ai_limit=ai_limit)
                logger.info("Categorization pass for user %s: %s", user_id, stats)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Background categorization job failed: %s", exc)


class EmailService:
    def __init__(self, gmail_service: GmailService | None = None) -> None:
        self.gmail = gmail_service or GmailService()
        self.categorizer = CategorizationService()

    async def get_primary_account(self, db: AsyncSession, user_id: UUID) -> Account:
        result = await db.execute(
            select(Account).where(
                Account.user_id == user_id,
                Account.is_primary.is_(True),
                Account.is_active.is_(True),
            )
        )
        account = result.scalar_one_or_none()
        if account is None:
            raise AppError("No connected Gmail account found", status_code=404)
        return account

    async def sync_inbox(
        self,
        db: AsyncSession,
        user: User,
        *,
        max_results: int = 100,
        sync_all: bool = False,
        incremental: bool = False,
        query: str | None = None,
    ) -> tuple[SyncInboxResponse, list[str]]:
        """Synchronous sync for API callers. New emails get deterministic categories
        immediately; AI categorization runs in a background job (categorize_recent_emails_job)."""
        account = await self.get_primary_account(db, user.id)

        if incremental and not sync_all and not query:
            return await self._sync_incremental(db, user, account)

        gmail_query = sanitize_gmail_query(query) if query else None

        if incremental and account.last_synced_at:
            after = account.last_synced_at.astimezone(UTC) - FALLBACK_WINDOW
            date_query = f"after:{int(after.timestamp())}"
            gmail_query = f"{date_query} {gmail_query}".strip() if gmail_query else date_query

        if sync_all:
            all_ids = await self.gmail.collect_query_message_ids(
                query=gmail_query or "",
                account=account,
                db=db,
            )
        else:
            all_ids, _ = await self.gmail.list_message_ids(
                account=account,
                db=db,
                query=gmail_query,
                max_results=min(max_results, 500),
            )

        # Always refresh metadata for listed IDs (new + existing) so read/star
        # state stays current; only brand-new IDs count toward new_count.
        ids_to_fetch = list(dict.fromkeys(all_ids))
        deferred_ids: list[str] = []

        if sync_all and len(ids_to_fetch) > FAST_SYNC_BATCH:
            deferred_ids = ids_to_fetch[FAST_SYNC_BATCH:]
            ids_to_fetch = ids_to_fetch[:FAST_SYNC_BATCH]

        access_token = await self.gmail.ensure_valid_access_token(account, db)
        messages = await self.gmail.fetch_messages_batch(access_token, ids_to_fetch)

        _emails, new_count, updated_count = await self._bulk_upsert_emails(db, user, account, messages)

        try:
            account.gmail_history_id = await self.gmail.get_history_id(account=account, db=db)
        except GmailReauthRequired:
            raise
        except AppError as exc:
            logger.warning("Could not refresh Gmail historyId: %s", exc)

        account.last_synced_at = datetime.now(UTC)
        await db.commit()
        await db.refresh(account)

        response = SyncInboxResponse(
            synced_count=len(all_ids),
            new_count=new_count,
            updated_count=updated_count,
            account_email=account.email,
            last_synced_at=account.last_synced_at,
        )
        return response, deferred_ids

    async def _sync_incremental(
        self,
        db: AsyncSession,
        user: User,
        account: Account,
    ) -> tuple[SyncInboxResponse, list[str]]:
        """Near real-time sync via the Gmail History API, with a paginated query fallback."""
        changes: GmailHistoryChanges | None = None
        if account.gmail_history_id:
            try:
                changes = await self.gmail.list_history_changes(
                    account=account,
                    db=db,
                    start_history_id=account.gmail_history_id,
                )
            except AppError as exc:
                # History ID expired / invalid: fall through to the query window.
                if exc.status_code not in {404, 400}:
                    raise
                logger.info(
                    "Gmail history sync unavailable for %s (%s); falling back to query window",
                    account.email,
                    exc.message,
                )
            if changes is not None and not changes.complete:
                logger.info("Gmail history for %s exceeded page limit; using query window", account.email)
                changes = None

        if changes is not None:
            return await self._apply_history_changes(db, user, account, changes)
        return await self._sync_query_window(db, user, account)

    async def _apply_history_changes(
        self,
        db: AsyncSession,
        user: User,
        account: Account,
        changes: GmailHistoryChanges,
    ) -> tuple[SyncInboxResponse, list[str]]:
        new_count = 0
        updated_count = 0
        deleted_ids = set(changes.deleted_ids)
        fetch_ids = [
            gid for gid in dict.fromkeys([*changes.added_ids, *changes.updated_ids]) if gid not in deleted_ids
        ]

        if fetch_ids:
            access_token = await self.gmail.ensure_valid_access_token(account, db)
            messages = await self.gmail.fetch_messages_batch(access_token, fetch_ids)
            _emails, new_count, updated_count = await self._bulk_upsert_emails(db, user, account, messages)

        deleted_count = await self._delete_emails_by_gmail_ids(db, account.id, list(deleted_ids))

        account.gmail_history_id = changes.history_id or await self.gmail.get_history_id(
            account=account, db=db
        )
        account.last_synced_at = datetime.now(UTC)
        await db.commit()
        await db.refresh(account)

        return (
            SyncInboxResponse(
                synced_count=len(fetch_ids) + len(deleted_ids),
                new_count=new_count,
                updated_count=updated_count + deleted_count,
                account_email=account.email,
                last_synced_at=account.last_synced_at,
            ),
            [],
        )

    async def _sync_query_window(
        self,
        db: AsyncSession,
        user: User,
        account: Account,
    ) -> tuple[SyncInboxResponse, list[str]]:
        """Re-list everything since the last sync (minus a safety margin), every page."""
        try:
            history_id = await self.gmail.get_history_id(account=account, db=db)
        except GmailReauthRequired:
            raise
        except AppError as exc:
            logger.warning("Could not seed Gmail historyId: %s", exc)
            history_id = account.gmail_history_id

        window = FALLBACK_WINDOW if account.last_synced_at else FALLBACK_WINDOW_FIRST_SYNC
        after = (account.last_synced_at or datetime.now(UTC)).astimezone(UTC) - window
        all_ids = await self.gmail.collect_query_message_ids(
            query=f"after:{int(after.timestamp())}",
            account=account,
            db=db,
        )
        access_token = await self.gmail.ensure_valid_access_token(account, db)
        messages = await self.gmail.fetch_messages_batch(access_token, all_ids)
        _emails, new_count, updated_count = await self._bulk_upsert_emails(db, user, account, messages)

        account.gmail_history_id = history_id
        account.last_synced_at = datetime.now(UTC)
        await db.commit()
        await db.refresh(account)

        return (
            SyncInboxResponse(
                synced_count=len(all_ids),
                new_count=new_count,
                updated_count=updated_count,
                account_email=account.email,
                last_synced_at=account.last_synced_at,
            ),
            [],
        )

    async def _delete_emails_by_gmail_ids(
        self,
        db: AsyncSession,
        account_id: UUID,
        gmail_ids: list[str],
    ) -> int:
        if not gmail_ids:
            return 0
        result = await db.execute(
            select(Email).where(
                Email.account_id == account_id,
                Email.gmail_id.in_(gmail_ids),
            )
        )
        rows = list(result.scalars().all())
        for email in rows:
            await db.delete(email)
        if rows:
            await db.flush()
        return len(rows)

    async def _reconcile_deleted(
        self,
        db: AsyncSession,
        account_id: UUID,
        listed_ids: set[str],
        *,
        created_before: datetime,
    ) -> int:
        """Delete rows Gmail no longer lists (deleted, trashed, spammed outside the app).

        Rows created after the sync started are kept: they came from a concurrent
        incremental sync and may postdate the listing.
        """
        result = await db.execute(
            select(Email.id, Email.gmail_id).where(
                Email.account_id == account_id,
                Email.created_at < created_before,
            )
        )
        rows = result.all()
        missing = [email_id for email_id, gmail_id in rows if gmail_id not in listed_ids]
        if not missing:
            return 0
        if len(rows) > RECONCILE_MIN_DB_ROWS and len(listed_ids) < len(rows) * RECONCILE_MIN_LISTED_SHARE:
            logger.warning(
                "Skipping deletion reconcile for account %s: Gmail listed %s ids but %s rows are stored",
                account_id,
                len(listed_ids),
                len(rows),
            )
            return 0

        for start in range(0, len(missing), 500):
            chunk = missing[start : start + 500]
            await db.execute(delete(Category).where(Category.email_id.in_(chunk)))
            await db.execute(delete(Summary).where(Summary.email_id.in_(chunk)))
            await db.execute(delete(Email).where(Email.id.in_(chunk)))
        await db.flush()
        logger.info("Removed %s emails no longer present in Gmail for account %s", len(missing), account_id)
        return len(missing)

    async def _existing_gmail_ids(self, db: AsyncSession, account_id: UUID) -> set[str]:
        result = await db.execute(
            select(Email.gmail_id).where(Email.account_id == account_id)
        )
        return set(result.scalars().all())

    async def _stale_gmail_ids(self, db: AsyncSession, account_id: UUID) -> set[str]:
        result = await db.execute(
            select(Email.gmail_id).where(
                Email.account_id == account_id,
                Email.signals_version < SIGNALS_VERSION,
            )
        )
        return set(result.scalars().all())

    @staticmethod
    def _apply_message(email: Email, gmail_message: GmailMessage) -> None:
        email.thread_id = gmail_message.thread_id
        email.sender = gmail_message.sender
        email.sender_name = gmail_message.sender_name
        email.subject = gmail_message.subject[:998]
        email.preview = gmail_message.preview or email.preview
        if gmail_message.body_text is not None:
            email.body_text = gmail_message.body_text
        if gmail_message.body_html is not None:
            email.body_html = gmail_message.body_html
        email.received_at = gmail_message.received_at
        email.is_read = gmail_message.is_read
        email.is_starred = gmail_message.is_starred
        email.is_important = gmail_message.is_important
        email.labels = json.dumps(gmail_message.labels)
        email.recipients = ",".join(gmail_message.recipients) or None
        email.list_id = (gmail_message.list_id or "")[:255] or None
        email.is_bulk = gmail_message.is_bulk
        email.is_automated = gmail_message.is_automated
        email.signals_version = SIGNALS_VERSION

    async def _bulk_upsert_emails(
        self,
        db: AsyncSession,
        user: User,
        account: Account,
        gmail_messages: list[GmailMessage],
    ) -> tuple[list[Email], int, int]:
        """Upsert fetched messages and classify them. Trash/spam messages are removed instead."""
        if not gmail_messages:
            return [], 0, 0

        excluded = [m.gmail_id for m in gmail_messages if EXCLUDED_LABELS.intersection(m.labels)]
        if excluded:
            await self._delete_emails_by_gmail_ids(db, account.id, excluded)
            excluded_set = set(excluded)
            gmail_messages = [m for m in gmail_messages if m.gmail_id not in excluded_set]
            if not gmail_messages:
                return [], 0, 0

        gmail_ids = [message.gmail_id for message in gmail_messages]
        result = await db.execute(
            select(Email).where(
                Email.account_id == account.id,
                Email.gmail_id.in_(gmail_ids),
            )
        )
        existing_map = {email.gmail_id: email for email in result.scalars().all()}

        new_count = 0
        updated_count = 0
        emails: list[Email] = []

        for gmail_message in gmail_messages:
            email = existing_map.get(gmail_message.gmail_id)
            if email is None:
                email = Email(
                    user_id=user.id,
                    account_id=account.id,
                    gmail_id=gmail_message.gmail_id,
                )
                db.add(email)
                existing_map[gmail_message.gmail_id] = email
                new_count += 1
            else:
                updated_count += 1
            self._apply_message(email, gmail_message)
            emails.append(email)

        await db.flush()
        await self.categorizer.classify_emails(db, user, emails)
        return emails, new_count, updated_count

    async def _upsert_email(
        self,
        db: AsyncSession,
        user: User,
        account: Account,
        gmail_message: GmailMessage,
    ) -> tuple[Email, bool]:
        result = await db.execute(
            select(Email).where(
                Email.account_id == account.id,
                Email.gmail_id == gmail_message.gmail_id,
            )
        )
        email = result.scalar_one_or_none()
        is_new = email is None

        if email is None:
            email = Email(
                user_id=user.id,
                account_id=account.id,
                gmail_id=gmail_message.gmail_id,
            )
            db.add(email)

        self._apply_message(email, gmail_message)
        await db.flush()
        await self.categorizer.classify_emails(db, user, [email])
        return email, is_new

    async def list_emails(
        self,
        db: AsyncSession,
        user: User,
        *,
        page: int = 1,
        page_size: int = 20,
        is_read: bool | None = None,
        is_important: bool | None = None,
        is_priority: bool | None = None,
        has_summary: bool | None = None,
        category: EmailCategory | None = None,
        search: str | None = None,
        sort_by: EmailSortField = EmailSortField.RECEIVED_AT,
        sort_order: SortOrder = SortOrder.DESC,
    ) -> EmailListResponse:
        page, page_size = clamp_pagination(page, page_size)

        filters = [Email.user_id == user.id]

        if is_read is not None:
            filters.append(Email.is_read.is_(is_read))
        if is_important is not None:
            filters.append(Email.is_important.is_(is_important))
        if is_priority is True:
            filters.append(Email.priority_score >= PRIORITY_THRESHOLD)
        elif is_priority is False:
            filters.append(Email.priority_score < PRIORITY_THRESHOLD)

        count_query = select(func.count(Email.id)).where(*filters)
        base_query = (
            select(Email)
            .where(*filters)
            .options(selectinload(Email.category), selectinload(Email.summary))
        )

        if has_summary is True:
            summary_filter = Summary.summary_text.isnot(None)
            count_query = count_query.join(Summary, Summary.email_id == Email.id).where(summary_filter)
            base_query = base_query.join(Summary, Summary.email_id == Email.id).where(summary_filter)
        elif has_summary is False:
            summary_filter = or_(Summary.id.is_(None), Summary.summary_text.is_(None))
            count_query = (
                count_query.outerjoin(Summary, Summary.email_id == Email.id).where(summary_filter)
            )
            base_query = base_query.outerjoin(Summary, Summary.email_id == Email.id).where(summary_filter)

        if category is not None:
            category_filter = Category.category == category
            count_query = count_query.join(Category).where(category_filter)
            base_query = base_query.join(Category).where(category_filter)

        if search:
            term = f"%{sanitize_string(search, max_length=200)}%"
            search_filter = or_(
                Email.subject.ilike(term),
                Email.sender.ilike(term),
                Email.preview.ilike(term),
            )
            count_query = count_query.where(search_filter)
            base_query = base_query.where(search_filter)

        count_result = await db.execute(count_query)
        total = count_result.scalar_one()

        sort_column = {
            EmailSortField.RECEIVED_AT: Email.received_at,
            EmailSortField.SUBJECT: Email.subject,
            EmailSortField.SENDER: Email.sender,
        }[sort_by]

        ordered = base_query.order_by(
            sort_column.asc() if sort_order == SortOrder.ASC else sort_column.desc()
        )

        offset = (page - 1) * page_size
        result = await db.execute(ordered.offset(offset).limit(page_size))
        emails = result.scalars().all()

        items = [self._to_list_item(email) for email in emails]
        return EmailListResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            has_more=(offset + len(items)) < total,
        )

    async def get_email(
        self,
        db: AsyncSession,
        user: User,
        email_id: UUID,
    ) -> EmailDetail:
        async def load_email() -> Email | None:
            result = await db.execute(
                select(Email)
                .where(Email.id == email_id, Email.user_id == user.id)
                .options(selectinload(Email.category), selectinload(Email.summary))
            )
            return result.scalar_one_or_none()

        email = await load_email()
        if email is None:
            raise AppError("Email not found", status_code=404)

        if not email.body_text and not email.body_html:
            account = await self.get_primary_account(db, user.id)
            try:
                full_message = await self.gmail.get_message(
                    account=account,
                    db=db,
                    message_id=email.gmail_id,
                    message_format="full",
                )
                if full_message.body_text is not None:
                    email.body_text = full_message.body_text
                if full_message.body_html is not None:
                    email.body_html = full_message.body_html
                if full_message.preview:
                    email.preview = full_message.preview
                await db.commit()
                email = await load_email()
                if email is None:
                    raise AppError("Email not found", status_code=404)
            except AppError as exc:
                logger.warning(
                    "Gmail body fetch failed for %s — returning preview only: %s",
                    email.gmail_id,
                    exc.message,
                )
                if email.preview and not email.body_text:
                    email.body_text = email.preview

        return self._to_detail(email)

    def _to_list_item(self, email: Email) -> EmailListItem:
        from sqlalchemy import inspect as sa_inspect

        from app.schemas.email import EmailCategoryLabel

        state = sa_inspect(email)
        category = None
        category_row = None
        if "category" not in state.unloaded and email.category is not None:
            category_row = email.category
            category = EmailCategoryLabel(category_row.category.value)

        summary_text = None
        if "summary" not in state.unloaded and email.summary is not None:
            summary_text = email.summary.summary_text

        return EmailListItem(
            id=email.id,
            gmail_id=email.gmail_id,
            sender=email.sender,
            sender_name=email.sender_name,
            subject=email.subject,
            preview=email.preview,
            received_at=email.received_at,
            is_read=email.is_read,
            is_starred=email.is_starred,
            is_important=email.is_important,
            priority_score=email.priority_score or 0,
            is_priority=(email.priority_score or 0) >= PRIORITY_THRESHOLD,
            category=category,
            category_source=category_row.source if category_row else None,
            category_confidence=category_row.confidence if category_row else None,
            category_reason=category_row.reason if category_row else None,
            summary_text=summary_text,
        )

    def _to_detail(self, email: Email) -> EmailDetail:
        labels: list[str] = []
        if email.labels:
            try:
                labels = json.loads(email.labels)
            except json.JSONDecodeError:
                labels = []

        list_item = self._to_list_item(email)
        return EmailDetail(
            **list_item.model_dump(),
            thread_id=email.thread_id,
            body_text=email.body_text,
            body_html=email.body_html,
            labels=labels,
        )
