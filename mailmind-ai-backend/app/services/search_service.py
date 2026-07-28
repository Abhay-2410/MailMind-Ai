import logging
import re
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import AppError
from app.models.email import Email
from app.models.search_history import SearchHistory
from app.models.user import User
from app.schemas.search import SearchHistoryItem, SearchResponse
from app.services.ai_service import AIService
from app.services.email_service import EmailService
from app.utils.validators import sanitize_gmail_query

logger = logging.getLogger(__name__)


def heuristic_gmail_query(query: str) -> str:
    """Best-effort natural-language -> Gmail query without an AI call.

    Used as a fallback when the AI translator is unavailable (e.g. the free
    model is rate-limited) so search still returns useful results.
    """
    text = query.lower().strip()
    parts: list[str] = []

    if "unread" in text:
        parts.append("is:unread")
    if "starred" in text or "flagged" in text:
        parts.append("is:starred")
    if "important" in text:
        parts.append("is:important")
    if "attachment" in text:
        parts.append("has:attachment")

    if "today" in text:
        parts.append("newer_than:1d")
    elif "yesterday" in text:
        parts.append("newer_than:2d")
    elif "week" in text:
        parts.append("newer_than:7d")
    elif "month" in text:
        parts.append("newer_than:30d")
    elif "year" in text:
        parts.append("newer_than:365d")

    sender = re.search(r"from\s+([a-z0-9._%+-]+@[a-z0-9.-]+|[a-z0-9._-]+)", text)
    if sender:
        parts.append(f"from:{sender.group(1)}")

    # Strip control words so leftover keywords become a free-text search.
    stop = {
        "show", "me", "my", "all", "emails", "email", "mails", "mail", "find",
        "search", "for", "the", "from", "this", "with", "unread", "starred",
        "important", "attachment", "attachments", "today", "yesterday", "week",
        "month", "year", "flagged", "messages", "get", "list",
    }
    keywords = [w for w in re.findall(r"[a-z0-9]+", text) if w not in stop and not w.isdigit()]
    if keywords and sender is None:
        parts.append(" ".join(keywords[:5]))

    return " ".join(parts).strip() or query.strip()


class SearchService:
    def __init__(
        self,
        ai_service: AIService | None = None,
        email_service: EmailService | None = None,
    ) -> None:
        self.ai = ai_service or AIService()
        self.email = email_service or EmailService()

    async def search(
        self,
        db: AsyncSession,
        user: User,
        *,
        query: str,
        max_results: int = 50,
    ) -> SearchResponse:
        gmail_query_raw: str
        explanation: str
        model_used: str | None

        try:
            translation = await self.ai.translate_search_query(db, user, query)
            gmail_query_raw = translation.gmail_query
            explanation = translation.explanation
            model_used = translation.model_used
        except AppError as exc:
            gmail_query_raw = heuristic_gmail_query(query)
            explanation = (
                "AI translation was unavailable, so a keyword-based search was used instead."
            )
            model_used = None
            logger.warning("Search AI translation failed, using heuristic: %s", exc)

        account = await self.email.get_primary_account(db, user.id)
        access_token = await self.email.gmail.ensure_valid_access_token(account, db)

        gmail_query = sanitize_gmail_query(gmail_query_raw)
        fetch_result = await self.email.gmail.fetch_messages(
            access_token,
            query=gmail_query,
            max_results=max_results,
        )

        gmail_ids: list[str] = []
        for gmail_message in fetch_result.messages:
            await self.email._upsert_email(db, user, account, gmail_message)
            gmail_ids.append(gmail_message.gmail_id)

        account.last_synced_at = datetime.now(UTC)

        emails: list[Email] = []
        if gmail_ids:
            email_result = await db.execute(
                select(Email)
                .where(Email.user_id == user.id, Email.gmail_id.in_(gmail_ids))
                .options(selectinload(Email.category), selectinload(Email.summary))
                .order_by(Email.received_at.desc())
            )
            emails = list(email_result.scalars().all())

        db.add(
            SearchHistory(
                user_id=user.id,
                natural_query=query,
                gmail_query=gmail_query_raw,
                results_count=len(emails),
                model_used=model_used,
            )
        )
        await db.commit()

        items = [self.email._to_list_item(email) for email in emails]
        return SearchResponse(
            natural_query=query,
            gmail_query=gmail_query_raw,
            explanation=explanation,
            model_used=model_used,
            results=items,
            total=len(items),
        )

    async def list_history(
        self,
        db: AsyncSession,
        user: User,
        *,
        limit: int = 10,
    ) -> list[SearchHistoryItem]:
        result = await db.execute(
            select(SearchHistory)
            .where(SearchHistory.user_id == user.id)
            .order_by(SearchHistory.created_at.desc())
            .limit(limit)
        )
        rows = result.scalars().all()
        return [SearchHistoryItem.model_validate(row) for row in rows]
