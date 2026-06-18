import json
import logging
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import AppError
from app.models.account import Account
from app.models.category import Category, EmailCategory
from app.models.email import Email
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
from app.utils.validators import clamp_pagination, sanitize_gmail_query, sanitize_string

logger = logging.getLogger(__name__)


async def categorize_recent_emails_job(user_id: UUID, limit: int = 50) -> None:
    """Background job: categorize the user's most recent uncategorized emails.

    Runs in its own DB session after the sync response is returned so the
    request stays fast. Failures are logged, never raised.
    """
    from app.db.session import AsyncSessionLocal

    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(Email.id)
                .where(Email.user_id == user_id)
                .order_by(Email.received_at.desc())
                .limit(limit)
            )
            email_ids = list(result.scalars().all())
            count = await EmailService().categorize_user_emails(db, user_id, email_ids)
            logger.info("Background categorization tagged %s emails for user %s", count, user_id)
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
        max_results: int = 50,
        sync_all: bool = False,
        query: str | None = None,
        categorize: bool = True,
    ) -> SyncInboxResponse:
        account = await self.get_primary_account(db, user.id)
        access_token = await self.gmail.ensure_valid_access_token(account, db)

        gmail_query = sanitize_gmail_query(query) if query else None

        if sync_all:
            result = await self.gmail.fetch_all_messages(
                access_token,
                query=gmail_query,
                page_size=min(max_results, 500),
                max_total=2000,
            )
        else:
            result = await self.gmail.fetch_messages(
                access_token,
                query=gmail_query,
                max_results=max_results,
            )

        new_count = 0
        updated_count = 0
        synced_emails: list[Email] = []

        for gmail_message in result.messages:
            email, created = await self._upsert_email(db, user, account, gmail_message)
            synced_emails.append(email)
            if created:
                new_count += 1
            else:
                updated_count += 1

        account.last_synced_at = datetime.now(UTC)
        await db.commit()
        await db.refresh(account)

        if categorize and synced_emails:
            await self._categorize_uncategorized(db, user, synced_emails)

        return SyncInboxResponse(
            synced_count=len(result.messages),
            new_count=new_count,
            updated_count=updated_count,
            account_email=account.email,
            last_synced_at=account.last_synced_at,
        )

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
        email.preview = gmail_message.preview
        email.body_text = gmail_message.body_text
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
        base_query = select(Email).where(*filters).options(selectinload(Email.category))

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
        result = await db.execute(
            select(Email)
            .where(Email.id == email_id, Email.user_id == user.id)
            .options(selectinload(Email.category))
        )
        email = result.scalar_one_or_none()
        if email is None:
            raise AppError("Email not found", status_code=404)
        return self._to_detail(email)

    def _to_list_item(self, email: Email) -> EmailListItem:
        from app.schemas.email import EmailCategoryLabel

        category = (
            EmailCategoryLabel(email.category.category.value)
            if email.category
            else None
        )
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
