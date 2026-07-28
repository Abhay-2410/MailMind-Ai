import logging
import re
import time
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.prompts.assistant import ASSISTANT_SYSTEM, build_assistant_prompt
from app.core.exceptions import AppError
from app.models.ai_usage import AIActionType
from app.models.email import Email
from app.models.user import User
from app.schemas.ai import AssistantResponse
from app.services.ai_service import AIService

logger = logging.getLogger(__name__)

ASSISTANT_MAX_TOKENS = 220
ASSISTANT_RECENT_LIMIT = 8
ASSISTANT_MATCH_LIMIT = 12
ASSISTANT_PREVIEW_CHARS = 160
ASSISTANT_BODY_CHARS = 500

_STOP_WORDS = frozenset(
    {
        "the",
        "and",
        "for",
        "are",
        "but",
        "not",
        "you",
        "all",
        "can",
        "had",
        "her",
        "was",
        "one",
        "our",
        "out",
        "has",
        "have",
        "been",
        "from",
        "that",
        "this",
        "with",
        "what",
        "when",
        "where",
        "which",
        "who",
        "whom",
        "your",
        "about",
        "into",
        "than",
        "then",
        "them",
        "they",
        "their",
        "there",
        "these",
        "those",
        "please",
        "could",
        "would",
        "should",
        "summarize",
        "summary",
        "email",
        "emails",
        "inbox",
        "mail",
        "message",
        "messages",
        "tell",
        "show",
        "find",
        "give",
        "list",
        "any",
        "related",
        "task",
        "help",
        "need",
        "want",
    }
)


def extract_search_terms(question: str) -> list[str]:
    words = re.findall(r"[a-zA-Z0-9]{3,}", question.lower())
    terms: list[str] = []
    for word in words:
        if word in _STOP_WORDS or word in terms:
            continue
        terms.append(word)
        if len(terms) >= 6:
            break
    return terms


class AssistantService(AIService):
    async def _resolve_assistant_model(self, db: AsyncSession, user_id: UUID) -> tuple[str, str]:
        """Inbox assistant always uses Groq — no OpenRouter fallback."""
        _ = db, user_id
        if not self.settings.GROQ_API_KEY:
            raise AppError(
                "Groq API key is not configured. Set GROQ_API_KEY in the backend .env.",
                status_code=503,
            )
        return "groq", self.settings.GROQ_ASSISTANT_MODEL

    async def _load_context_emails(
        self,
        db: AsyncSession,
        user_id: UUID,
        question: str,
    ) -> list[Email]:
        """Load recent emails plus keyword matches so topic questions stay fast and relevant."""
        terms = extract_search_terms(question)
        by_id: dict[UUID, Email] = {}

        recent_result = await db.execute(
            select(Email)
            .where(Email.user_id == user_id)
            .order_by(Email.received_at.desc())
            .limit(ASSISTANT_RECENT_LIMIT)
        )
        for email in recent_result.scalars().all():
            by_id[email.id] = email

        if terms:
            filters = []
            for term in terms:
                pattern = f"%{term}%"
                filters.extend(
                    [
                        Email.subject.ilike(pattern),
                        Email.preview.ilike(pattern),
                        Email.sender.ilike(pattern),
                        Email.body_text.ilike(pattern),
                    ]
                )
            match_result = await db.execute(
                select(Email)
                .where(Email.user_id == user_id, or_(*filters))
                .order_by(Email.received_at.desc())
                .limit(ASSISTANT_MATCH_LIMIT)
            )
            for email in match_result.scalars().all():
                by_id[email.id] = email

        return sorted(by_id.values(), key=lambda item: item.received_at, reverse=True)

    def _format_email_context(self, emails: list[Email], *, question_terms: list[str]) -> str:
        if not emails:
            return "No emails synced yet."

        lines: list[str] = []
        for email in emails:
            haystack = " ".join(
                part
                for part in (email.subject, email.preview or "", email.body_text or "", email.sender)
                if part
            ).lower()
            is_match = bool(question_terms) and any(term in haystack for term in question_terms)
            snippet_source = email.body_text or email.preview or ""
            snippet = snippet_source[: ASSISTANT_BODY_CHARS if is_match else ASSISTANT_PREVIEW_CHARS]
            lines.append(
                f"- [{email.received_at.date()}] From: {email.sender} | "
                f"Subject: {email.subject} | Read: {email.is_read} | "
                f"Snippet: {snippet}"
            )
        return "\n".join(lines)

    async def ask(
        self,
        db: AsyncSession,
        user: User,
        question: str,
    ) -> AssistantResponse:
        started = time.perf_counter()
        terms = extract_search_terms(question)
        emails = await self._load_context_emails(db, user.id, question)
        context = self._format_email_context(emails, question_terms=terms)

        provider_name, model_id = await self._resolve_assistant_model(db, user.id)
        provider = self._get_provider(provider_name)

        completion = await provider.complete(
            model=model_id,
            system_prompt=ASSISTANT_SYSTEM,
            user_prompt=build_assistant_prompt(question=question, context=context),
            temperature=0.2,
            max_tokens=ASSISTANT_MAX_TOKENS,
        )

        await self._track_usage(
            db,
            user.id,
            AIActionType.ASSISTANT,
            provider=completion.provider,
            model=completion.model,
            prompt_tokens=completion.prompt_tokens,
            completion_tokens=completion.completion_tokens,
            total_tokens=completion.total_tokens,
            metadata={"question": question[:200], "email_count": len(emails)},
        )
        await db.commit()

        elapsed_ms = (time.perf_counter() - started) * 1000
        logger.info(
            "Assistant answered in %.0fms model=%s emails=%s prompt_tokens=%s",
            elapsed_ms,
            model_id,
            len(emails),
            completion.prompt_tokens,
        )

        return AssistantResponse(answer=completion.content, model_used=model_id)
