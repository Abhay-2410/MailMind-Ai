import json
import logging
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import AppError
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
from app.services.gmail_service import GmailMessage, GmailService
from app.utils.gmail_categories import infer_category_from_gmail_labels
from app.utils.validators import clamp_pagination, sanitize_gmail_query, sanitize_string

logger = logging.getLogger(__name__)

FAST_SYNC_BATCH = 500
GMAIL_LIST_PAGE_SIZE = 500
# Inbox first for fast UI, then the rest of the mailbox (archives, sent, etc.).
SYNC_PHASE_QUERIES = ("in:inbox", "")
CATEGORIZE_AFTER_FULL_SYNC = 5000


async def run_full_inbox_sync_job(user_id: UUID) -> None:
    """Paginated full Gmail sync — inbox first, then remaining mail, in parallel batches."""
    from app.db.session import AsyncSessionLocal
    from app.services.sync_jobs import inbox_sync_job_store

    job = inbox_sync_job_store.get_or_create(user_id)

    try:
        async with AsyncSessionLocal() as db:
            service = EmailService()
            result = await db.execute(select(User).where(User.id == user_id))
            user = result.scalar_one_or_none()
            if user is None:
                await inbox_sync_job_store.fail(job, "User not found")
                return

            account = await service.get_primary_account(db, user.id)
            existing_ids = await service._existing_gmail_ids(db, account.id)
            counters = {"listed": 0, "fetched": 0, "new": 0, "updated": 0}

            for phase_query in SYNC_PHASE_QUERIES:
                page_token: str | None = None
                while True:
                    ids, page_token = await service.gmail.list_message_ids(
                        account=account,
                        db=db,
                        query=phase_query or None,
                        max_results=GMAIL_LIST_PAGE_SIZE,
                        page_token=page_token,
                    )
                    counters["listed"] += len(ids)
                    ids_to_fetch = [gid for gid in ids if gid not in existing_ids]

                    for start in range(0, len(ids_to_fetch), FAST_SYNC_BATCH):
                        chunk = ids_to_fetch[start : start + FAST_SYNC_BATCH]
                        if not chunk:
                            continue
                        access_token = await service.gmail.ensure_valid_access_token(account, db)
                        messages = await service.gmail.fetch_messages_batch(access_token, chunk)
                        _emails, new_count, updated_count = await service._bulk_upsert_emails(
                            db, user, account, messages
                        )
                        counters["fetched"] += len(messages)
                        counters["new"] += new_count
                        counters["updated"] += updated_count
                        existing_ids.update(chunk)
                        await db.commit()
                        await inbox_sync_job_store.update(
                            job,
                            listed_count=counters["listed"],
                            fetched_count=counters["fetched"],
                            new_count=counters["new"],
                            updated_count=counters["updated"],
                        )

                    await inbox_sync_job_store.update(job, listed_count=counters["listed"])
                    if not page_token:
                        break

            await service.apply_gmail_categories_for_user(db, user.id)
            try:
                account.gmail_history_id = await service.gmail.get_history_id(
                    account=account, db=db
                )
            except AppError as exc:
                logger.warning("Could not refresh Gmail historyId after full sync: %s", exc)
            account.last_synced_at = datetime.now(UTC)
            await db.commit()

        await inbox_sync_job_store.update(job, phase="categorizing")
        await categorize_recent_emails_job(user_id, CATEGORIZE_AFTER_FULL_SYNC)
        await inbox_sync_job_store.complete(job)
        logger.info(
            "Full inbox sync completed for user %s: listed=%s fetched=%s new=%s",
            user_id,
            counters["listed"],
            counters["fetched"],
            counters["new"],
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Full inbox sync failed for user %s: %s", user_id, exc)
        await inbox_sync_job_store.fail(job, str(exc))


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
            await service.apply_gmail_categories_for_user(db, user.id)
            account.last_synced_at = datetime.now(UTC)
            await db.commit()
            logger.info(
                "Background sync stored %s emails for user %s",
                len(messages),
                user_id,
            )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Background email sync job failed: %s", exc)


async def categorize_recent_emails_job(user_id: UUID, limit: int = 500) -> None:
    """Background job: apply Gmail labels then AI-categorize remaining emails."""
    from app.db.session import AsyncSessionLocal

    try:
        async with AsyncSessionLocal() as db:
            service = EmailService()
            gmail_count = await service.apply_gmail_categories_for_user(db, user_id)
            logger.info("Gmail label categories applied to %s emails for user %s", gmail_count, user_id)

            result = await db.execute(select(User).where(User.id == user_id))
            user = result.scalar_one_or_none()
            if user is None:
                return

            ai_total = 0
            while ai_total < limit:
                pending = await service.get_uncategorized_emails(db, user_id, limit=50)
                if not pending:
                    break
                from app.services.ai_service import AIService

                count = await AIService().categorize_emails(db, user, pending)
                ai_total += count
                if count == 0:
                    break

            logger.info(
                "Background categorization tagged %s emails via AI for user %s",
                ai_total,
                user_id,
            )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Background categorization job failed: %s", exc)


class EmailService:
    def __init__(self, gmail_service: GmailService | None = None) -> None:
        self.gmail = gmail_service or GmailService()

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
        categorize: bool = True,
    ) -> tuple[SyncInboxResponse, list[str]]:
        account = await self.get_primary_account(db, user.id)

        if incremental and not sync_all and not query:
            return await self._sync_incremental(db, user, account, max_results=max_results)

        gmail_query = sanitize_gmail_query(query) if query else None

        if incremental and account.last_synced_at:
            after = account.last_synced_at.astimezone(UTC) - timedelta(minutes=15)
            date_query = f"after:{after.year}/{after.month}/{after.day}"
            gmail_query = f"{date_query} {gmail_query}".strip() if gmail_query else date_query

        if sync_all:
            all_ids = await self.gmail.collect_query_message_ids(
                query=gmail_query or "",
                account=account,
                db=db,
            )
        elif incremental:
            all_ids, _ = await self.gmail.list_message_ids(
                account=account,
                db=db,
                query=gmail_query,
                max_results=min(max_results, 500),
            )
        else:
            all_ids, _ = await self.gmail.list_message_ids(
                account=account,
                db=db,
                query=gmail_query,
                max_results=max_results,
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

        synced_emails, new_count, updated_count = await self._bulk_upsert_emails(
            db, user, account, messages
        )

        try:
            account.gmail_history_id = await self.gmail.get_history_id(account=account, db=db)
        except AppError as exc:
            logger.warning("Could not refresh Gmail historyId: %s", exc)

        account.last_synced_at = datetime.now(UTC)
        await db.commit()
        await db.refresh(account)

        if categorize and synced_emails:
            await self._categorize_uncategorized(db, user, synced_emails)

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
        *,
        max_results: int = 200,
    ) -> tuple[SyncInboxResponse, list[str]]:
        """Near real-time sync via Gmail History API, with query fallback."""
        new_count = 0
        updated_count = 0
        deleted_count = 0
        listed = 0

        history_id = account.gmail_history_id
        if history_id:
            try:
                changes = await self.gmail.list_history_changes(
                    account=account,
                    db=db,
                    start_history_id=history_id,
                )
                fetch_ids = list(dict.fromkeys([*changes.added_ids, *changes.updated_ids]))
                listed = len(fetch_ids) + len(changes.deleted_ids)

                if fetch_ids:
                    access_token = await self.gmail.ensure_valid_access_token(account, db)
                    messages = await self.gmail.fetch_messages_batch(
                        access_token, fetch_ids[: max(max_results, 200)]
                    )
                    _emails, new_count, updated_count = await self._bulk_upsert_emails(
                        db, user, account, messages
                    )

                if changes.deleted_ids:
                    deleted_count = await self._delete_emails_by_gmail_ids(
                        db, account.id, changes.deleted_ids
                    )

                if changes.history_id:
                    account.gmail_history_id = changes.history_id
                else:
                    account.gmail_history_id = await self.gmail.get_history_id(
                        account=account, db=db
                    )

                account.last_synced_at = datetime.now(UTC)
                await db.commit()
                await db.refresh(account)

                return (
                    SyncInboxResponse(
                        synced_count=listed,
                        new_count=new_count,
                        updated_count=updated_count + deleted_count,
                        account_email=account.email,
                        last_synced_at=account.last_synced_at,
                    ),
                    [],
                )
            except AppError as exc:
                # History ID expired / invalid — fall through to recent query sync.
                if exc.status_code not in {404, 400}:
                    raise
                logger.info(
                    "Gmail history sync unavailable for %s (%s); falling back to recent query",
                    account.email,
                    exc.message,
                )
                account.gmail_history_id = None

        after = (account.last_synced_at or datetime.now(UTC)).astimezone(UTC) - timedelta(hours=6)
        date_query = f"after:{after.year}/{after.month}/{after.day}"
        all_ids, _ = await self.gmail.list_message_ids(
            account=account,
            db=db,
            query=date_query,
            max_results=min(max(max_results, 100), 500),
        )
        listed = len(all_ids)
        access_token = await self.gmail.ensure_valid_access_token(account, db)
        messages = await self.gmail.fetch_messages_batch(access_token, all_ids)
        _emails, new_count, updated_count = await self._bulk_upsert_emails(
            db, user, account, messages
        )
        try:
            account.gmail_history_id = await self.gmail.get_history_id(account=account, db=db)
        except AppError as exc:
            logger.warning("Could not seed Gmail historyId: %s", exc)
        account.last_synced_at = datetime.now(UTC)
        await db.commit()
        await db.refresh(account)

        return (
            SyncInboxResponse(
                synced_count=listed,
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

    async def _categorize_uncategorized(
        self,
        db: AsyncSession,
        user: User,
        emails: list[Email],
    ) -> None:
        """Categorize any synced emails that don't yet have a category.

        Imported lazily to avoid a circular import and wrapped so AI failures
        never break inbox sync.
        """
        from app.services.ai_service import AIService

        pending = await self._pending_categorization(db, user.id, [e.id for e in emails])
        if not pending:
            return

        try:
            await AIService().categorize_emails(db, user, pending)
        except Exception as exc:  # noqa: BLE001
            await db.rollback()
            logger.warning("Auto-categorization during sync failed: %s", exc)

    async def _pending_categorization(
        self,
        db: AsyncSession,
        user_id: UUID,
        email_ids: list[UUID],
    ) -> list[Email]:
        if not email_ids:
            return []
        existing = await db.execute(
            select(Category.email_id).where(Category.email_id.in_(email_ids))
        )
        categorized_ids = set(existing.scalars().all())
        pending_ids = [eid for eid in email_ids if eid not in categorized_ids]
        if not pending_ids:
            return []
        result = await db.execute(
            select(Email).where(Email.id.in_(pending_ids)).order_by(Email.received_at.desc())
        )
        return list(result.scalars().all())

    async def _existing_gmail_ids(self, db: AsyncSession, account_id: UUID) -> set[str]:
        result = await db.execute(
            select(Email.gmail_id).where(Email.account_id == account_id)
        )
        return set(result.scalars().all())

    async def _bulk_upsert_emails(
        self,
        db: AsyncSession,
        user: User,
        account: Account,
        gmail_messages: list[GmailMessage],
    ) -> tuple[list[Email], int, int]:
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
            is_new = email is None

            if email is None:
                email = Email(
                    user_id=user.id,
                    account_id=account.id,
                    gmail_id=gmail_message.gmail_id,
                )
                db.add(email)
                new_count += 1
            else:
                updated_count += 1

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
            emails.append(email)

        await db.flush()

        for email, gmail_message in zip(emails, gmail_messages, strict=True):
            await self._ensure_gmail_category(
                db,
                email.id,
                gmail_message.labels,
                gmail_message.is_important,
            )

        await db.flush()
        return emails, new_count, updated_count

    async def get_uncategorized_emails(
        self,
        db: AsyncSession,
        user_id: UUID,
        *,
        limit: int = 50,
    ) -> list[Email]:
        result = await db.execute(
            select(Email)
            .outerjoin(Category, Category.email_id == Email.id)
            .where(Email.user_id == user_id, Category.id.is_(None))
            .order_by(Email.received_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def apply_gmail_categories_for_user(
        self,
        db: AsyncSession,
        user_id: UUID,
    ) -> int:
        """Assign categories from Gmail labels for all emails missing a category."""
        result = await db.execute(
            select(Email)
            .outerjoin(Category, Category.email_id == Email.id)
            .where(Email.user_id == user_id, Category.id.is_(None))
        )
        applied = 0
        for email in result.scalars():
            inferred = infer_category_from_gmail_labels(
                email.labels,
                is_important=email.is_important,
            )
            if inferred is None:
                continue
            await self._ensure_gmail_category(
                db,
                email.id,
                [],
                email.is_important,
                category=inferred,
            )
            applied += 1

        if applied:
            await db.commit()
        return applied

    async def _ensure_gmail_category(
        self,
        db: AsyncSession,
        email_id: UUID,
        label_ids: list[str],
        is_important: bool,
        *,
        category: EmailCategory | None = None,
    ) -> None:
        existing = await db.execute(select(Category).where(Category.email_id == email_id))
        row = existing.scalar_one_or_none()
        if row is not None and row.model_used not in (None, "gmail"):
            return

        inferred = category or infer_category_from_gmail_labels(label_ids, is_important=is_important)
        if inferred is None:
            return

        if row is None:
            row = Category(email_id=email_id)
            db.add(row)
        row.category = inferred
        row.confidence = 1.0
        row.model_used = "gmail"
        await db.flush()

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

        await db.flush()
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
        if "category" not in state.unloaded and email.category is not None:
            category = EmailCategoryLabel(email.category.category.value)

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
            category=category,
            summary_text=summary_text,
        )

    async def categorize_user_emails(
        self,
        db: AsyncSession,
        user_id: UUID,
        email_ids: list[UUID],
    ) -> int:
        """Categorize a set of the user's emails (used by background jobs)."""
        from app.services.ai_service import AIService

        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if user is None:
            return 0

        pending = await self._pending_categorization(db, user_id, email_ids)
        if not pending:
            return 0
        return await AIService().categorize_emails(db, user, pending)

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
