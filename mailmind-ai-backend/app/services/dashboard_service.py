from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.account import Account
from app.models.ai_usage import AIActionType, AIUsage
from app.models.category import Category, EmailCategory
from app.models.email import Email
from app.models.user import User
from app.schemas.dashboard import (
    ActivityItem,
    ActivityType,
    CategoryStat,
    DashboardResponse,
    DashboardStats,
)

CATEGORY_LABELS: dict[EmailCategory, str] = {
    EmailCategory.IMPORTANT: "Important",
    EmailCategory.WORK: "Work",
    EmailCategory.PERSONAL: "Personal",
    EmailCategory.FINANCE: "Finance",
    EmailCategory.PROMOTIONS: "Promotions",
    EmailCategory.SOCIAL: "Social",
    EmailCategory.UPDATES: "Updates",
}

AI_ACTION_LABELS: dict[AIActionType, tuple[ActivityType, str]] = {
    AIActionType.SUMMARIZE: (ActivityType.AI_SUMMARIZE, "Generated email summary"),
    AIActionType.REPLY: (ActivityType.AI_REPLY, "Generated AI reply"),
    AIActionType.CATEGORIZE: (ActivityType.AI_CATEGORIZE, "Categorized email"),
    AIActionType.SEARCH: (ActivityType.AI_SEARCH, "Translated search query"),
    AIActionType.ASSISTANT: (ActivityType.AI_ASSISTANT, "Used inbox assistant"),
}


def _to_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


class DashboardService:
    async def get_dashboard(self, db: AsyncSession, user: User) -> DashboardResponse:
        stats = await self._get_stats(db, user.id)
        categories = await self._get_category_breakdown(db, user.id)
        recent_activity = await self._get_recent_activity(db, user.id)
        return DashboardResponse(
            stats=stats,
            categories=categories,
            recent_activity=recent_activity,
        )

    async def _get_stats(self, db: AsyncSession, user_id: UUID) -> DashboardStats:
        total = await db.scalar(
            select(func.count(Email.id)).where(Email.user_id == user_id)
        )
        unread = await db.scalar(
            select(func.count(Email.id)).where(
                Email.user_id == user_id,
                Email.is_read.is_(False),
            )
        )
        important = await db.scalar(
            select(func.count(Email.id)).where(
                Email.user_id == user_id,
                Email.is_important.is_(True),
            )
        )
        ai_actions = await db.scalar(
            select(func.count(AIUsage.id)).where(AIUsage.user_id == user_id)
        )
        categorized = await db.scalar(
            select(func.count(Category.id))
            .join(Email, Category.email_id == Email.id)
            .where(Email.user_id == user_id)
        )

        account_result = await db.execute(
            select(Account.last_synced_at).where(
                Account.user_id == user_id,
                Account.is_primary.is_(True),
            )
        )
        last_synced = account_result.scalar_one_or_none()

        return DashboardStats(
            total_emails=total or 0,
            unread_emails=unread or 0,
            important_emails=important or 0,
            ai_actions_saved=ai_actions or 0,
            categorized_emails=categorized or 0,
            last_synced_at=last_synced,
        )

    async def _get_category_breakdown(
        self,
        db: AsyncSession,
        user_id: UUID,
    ) -> list[CategoryStat]:
        result = await db.execute(
            select(Category.category, func.count(Category.id))
            .join(Email, Category.email_id == Email.id)
            .where(Email.user_id == user_id)
            .group_by(Category.category)
        )
        rows = result.all()
        total = sum(count for _, count in rows) or 1

        stats: list[CategoryStat] = []
        counts_by_category = {category: count for category, count in rows}

        for category in EmailCategory:
            count = counts_by_category.get(category, 0)
            stats.append(
                CategoryStat(
                    category=category.value,
                    label=CATEGORY_LABELS[category],
                    count=count,
                    percentage=round((count / total) * 100, 1) if count else 0.0,
                )
            )

        return sorted(stats, key=lambda item: item.count, reverse=True)

    async def _get_recent_activity(
        self,
        db: AsyncSession,
        user_id: UUID,
        limit: int = 12,
    ) -> list[ActivityItem]:
        activities: list[ActivityItem] = []

        email_result = await db.execute(
            select(Email)
            .where(Email.user_id == user_id)
            .order_by(Email.received_at.desc())
            .limit(6)
        )
        for email in email_result.scalars():
            activities.append(
                ActivityItem(
                    id=email.id,
                    type=ActivityType.EMAIL_RECEIVED,
                    title=email.subject or "(No subject)",
                    description=f"From {email.sender_name or email.sender}",
                    timestamp=email.received_at,
                )
            )

        ai_result = await db.execute(
            select(AIUsage)
            .where(AIUsage.user_id == user_id)
            .order_by(AIUsage.created_at.desc())
            .limit(6)
        )
        for usage in ai_result.scalars():
            activity_type, description = AI_ACTION_LABELS.get(
                usage.action_type,
                (ActivityType.AI_ASSISTANT, "AI action completed"),
            )
            activities.append(
                ActivityItem(
                    id=usage.id,
                    type=activity_type,
                    title=description,
                    description=f"Model: {usage.model}",
                    timestamp=usage.created_at,
                )
            )

        account_result = await db.execute(
            select(Account)
            .where(Account.user_id == user_id, Account.is_primary.is_(True))
            .limit(1)
        )
        account = account_result.scalar_one_or_none()
        if account and account.last_synced_at:
            activities.append(
                ActivityItem(
                    id=uuid4(),
                    type=ActivityType.INBOX_SYNC,
                    title="Inbox synced",
                    description=f"Account {account.email}",
                    timestamp=account.last_synced_at,
                )
            )

        activities.sort(key=lambda item: _to_utc(item.timestamp), reverse=True)
        return activities[:limit]
