import json
import logging
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.models import get_default_model_id, get_model_by_id, list_available_models, resolve_model_id
from app.ai.openrouter import get_provider
from app.ai.prompts.categorize import CATEGORIZE_SYSTEM, build_categorize_prompt
from app.ai.prompts.reply import REPLY_SYSTEM, build_reply_prompt
from app.ai.prompts.search import SEARCH_SYSTEM, build_search_prompt
from app.ai.prompts.summarize import SUMMARIZE_SYSTEM, build_summarize_prompt
from app.ai.provider import AICompletionResult, AIProvider
from app.core.config import Settings, get_settings
from app.core.exceptions import AppError
from app.models.ai_usage import AIActionType, AIUsage
from app.models.category import Category, CategorySource, EmailCategory
from app.models.email import Email
from app.models.summary import PriorityLevel as DBPriorityLevel
from app.models.summary import Summary
from app.models.user import User
from app.models.user_settings import UserSettings
from app.utils.ai_json import normalize_summary_payload, parse_ai_json
from app.schemas.ai import (
    AIModelResponse,
    CategorizeEmailResponse,
    EmailCategoryLabel,
    GenerateReplyResponse,
    PriorityLevel,
    SummarizeEmailResponse,
    TranslateSearchResponse,
)

logger = logging.getLogger(__name__)


class AIService:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def _default_groq_model(self) -> str:
        return self.settings.GROQ_ASSISTANT_MODEL or get_default_model_id()

    def _provider_key_available(self, provider: str) -> bool:
        if provider == "groq":
            return bool(self.settings.GROQ_API_KEY)
        if provider == "openrouter":
            return bool(self.settings.OPENROUTER_API_KEY)
        return False

    async def _resolve_model(self, db: AsyncSession, user_id: UUID) -> tuple[str, str]:
        """Honor the user's saved model when that provider's API key is configured."""
        result = await db.execute(select(UserSettings).where(UserSettings.user_id == user_id))
        user_settings = result.scalar_one_or_none()
        if user_settings:
            model = get_model_by_id(user_settings.ai_model)
            # Unknown ids are usually decommissioned models; fall through to the default.
            if model is not None and self._provider_key_available(model.provider.value):
                return model.provider.value, model.id

        if self.settings.GROQ_API_KEY:
            return "groq", resolve_model_id(self._default_groq_model())

        default_id = get_default_model_id()
        default = get_model_by_id(default_id)
        provider = default.provider.value if default else "openrouter"
        if self._provider_key_available(provider):
            return provider, default_id
        if self.settings.OPENROUTER_API_KEY:
            return "openrouter", default_id
        return provider, default_id

    def _get_provider(self, provider_name: str) -> AIProvider:
        return get_provider(provider_name, self.settings)

    async def _track_usage(
        self,
        db: AsyncSession,
        user_id: UUID,
        action_type: AIActionType,
        *,
        provider: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        total_tokens: int,
        metadata: dict | None = None,
    ) -> None:
        db.add(
            AIUsage(
                user_id=user_id,
                action_type=action_type,
                provider=provider,
                model=model,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
                metadata_json=metadata,
            )
        )
        await db.flush()

    async def list_models(self) -> list[AIModelResponse]:
        return [
            AIModelResponse(
                id=model.id,
                name=model.name,
                provider=model.provider.value,
                description=model.description,
                is_default=model.is_default,
            )
            for model in list_available_models()
        ]

    async def _get_user_email(
        self,
        db: AsyncSession,
        user_id: UUID,
        email_id: UUID,
    ) -> Email:
        result = await db.execute(
            select(Email).where(Email.id == email_id, Email.user_id == user_id)
        )
        email = result.scalar_one_or_none()
        if email is None:
            raise AppError("Email not found", status_code=404)
        return email

    async def _parse_summary_result(
        self,
        provider: AIProvider,
        model_id: str,
        user_prompt: str,
        result: AICompletionResult,
    ) -> dict[str, str | list[str]]:
        try:
            return normalize_summary_payload(parse_ai_json(result.content))
        except (ValueError, json.JSONDecodeError) as exc:
            logger.warning("Summary JSON parse failed, retrying with plain completion: %s", exc)

        retry = await provider.complete(
            model=model_id,
            system_prompt=SUMMARIZE_SYSTEM + "\nRespond with JSON only. No markdown.",
            user_prompt=user_prompt,
            temperature=0.1,
            max_tokens=2048,
        )
        try:
            return normalize_summary_payload(parse_ai_json(retry.content))
        except (ValueError, json.JSONDecodeError) as retry_exc:
            raise AppError("AI returned invalid summary format", status_code=502) from retry_exc

    async def summarize_email(
        self,
        db: AsyncSession,
        user: User,
        email_id: UUID,
    ) -> SummarizeEmailResponse:
        email = await self._get_user_email(db, user.id, email_id)
        provider_name, model_id = await self._resolve_model(db, user.id)
        provider = self._get_provider(provider_name)

        body = email.body_text or email.preview or ""
        user_prompt = build_summarize_prompt(
            sender=email.sender,
            subject=email.subject,
            received_at=email.received_at.isoformat(),
            body=body,
        )

        result = await provider.complete_json(
            model=model_id,
            system_prompt=SUMMARIZE_SYSTEM,
            user_prompt=user_prompt,
        )

        parsed = await self._parse_summary_result(provider, model_id, user_prompt, result)

        priority_raw = parsed["priority_level"]
        try:
            priority = PriorityLevel(priority_raw)
        except ValueError:
            priority = PriorityLevel.MEDIUM

        summary_result = await db.execute(select(Summary).where(Summary.email_id == email.id))
        summary = summary_result.scalar_one_or_none()
        if summary is None:
            summary = Summary(email_id=email.id)
            db.add(summary)

        summary.summary_text = parsed["summary_text"]
        summary.key_points = parsed["key_points"]
        summary.action_items = parsed["action_items"]
        summary.important_dates = parsed["important_dates"]
        summary.priority_level = DBPriorityLevel(priority.value)
        summary.model_used = model_id

        await self._track_usage(
            db,
            user.id,
            AIActionType.SUMMARIZE,
            provider=result.provider,
            model=result.model,
            prompt_tokens=result.prompt_tokens,
            completion_tokens=result.completion_tokens,
            total_tokens=result.total_tokens,
            metadata={"email_id": str(email_id)},
        )
        await db.commit()

        return SummarizeEmailResponse(
            email_id=email.id,
            summary_text=summary.summary_text or "",
            key_points=summary.key_points,
            action_items=summary.action_items,
            important_dates=summary.important_dates,
            priority_level=priority,
            model_used=model_id,
        )

    async def generate_reply(
        self,
        db: AsyncSession,
        user: User,
        email_id: UUID,
        style: str,
    ) -> GenerateReplyResponse:
        email = await self._get_user_email(db, user.id, email_id)
        provider_name, model_id = await self._resolve_model(db, user.id)
        provider = self._get_provider(provider_name)

        body = email.body_text or email.preview or ""
        user_prompt = build_reply_prompt(
            sender=email.sender,
            subject=email.subject,
            body=body,
            style=style,
        )

        result = await provider.complete(
            model=model_id,
            system_prompt=REPLY_SYSTEM,
            user_prompt=user_prompt,
            temperature=0.4,
        )

        await self._track_usage(
            db,
            user.id,
            AIActionType.REPLY,
            provider=result.provider,
            model=result.model,
            prompt_tokens=result.prompt_tokens,
            completion_tokens=result.completion_tokens,
            total_tokens=result.total_tokens,
            metadata={"email_id": str(email_id), "style": style},
        )
        await db.commit()

        from app.schemas.ai import ReplyStyle

        return GenerateReplyResponse(
            email_id=email.id,
            reply=result.content,
            style=ReplyStyle(style) if style in ReplyStyle._value2member_map_ else ReplyStyle.PROFESSIONAL,
            model_used=model_id,
        )

    async def categorize_email(
        self,
        db: AsyncSession,
        user: User,
        email_id: UUID,
    ) -> CategorizeEmailResponse:
        from app.services.categorization_service import CategorizationService, signals_for_email
        from app.services.classifier import CONTENT_CATEGORIES, compute_priority

        email = await self._get_user_email(db, user.id, email_id)
        provider_name, model_id = await self._resolve_model(db, user.id)
        provider = self._get_provider(provider_name)

        signals = signals_for_email(email)
        hints = [flag for flag, on in (("bulk", signals.is_bulk), ("automated", signals.is_automated)) if on]
        user_prompt = build_categorize_prompt(
            sender=email.sender,
            subject=email.subject,
            preview=email.preview or email.body_text or "",
            signals=", ".join(hints) or "none",
        )

        result = await provider.complete_json(
            model=model_id,
            system_prompt=CATEGORIZE_SYSTEM,
            user_prompt=user_prompt,
        )

        try:
            parsed = json.loads(result.content)
        except json.JSONDecodeError as exc:
            raise AppError("AI returned invalid category format", status_code=502) from exc

        category = self._coerce_category(parsed.get("category"))
        if category not in CONTENT_CATEGORIES:
            category = EmailCategory.UPDATES
        confidence = self._coerce_confidence(parsed.get("confidence"))

        category_result = await db.execute(select(Category).where(Category.email_id == email.id))
        category_row = category_result.scalar_one_or_none()
        if category_row is None:
            category_row = Category(email_id=email.id)
            db.add(category_row)

        if category_row.source != CategorySource.USER.value:
            category_row.category = category
            category_row.confidence = confidence
            category_row.model_used = model_id
            category_row.source = CategorySource.AI.value
            category_row.reason = f"AI ({model_id})"

        await self._track_usage(
            db,
            user.id,
            AIActionType.CATEGORIZE,
            provider=result.provider,
            model=result.model,
            prompt_tokens=result.prompt_tokens,
            completion_tokens=result.completion_tokens,
            total_tokens=result.total_tokens,
            metadata={"email_id": str(email_id)},
        )
        ctx = await CategorizationService(self).load_context(db, user)
        email.priority_score = compute_priority(signals, category_row.category, ctx)
        await db.commit()

        return CategorizeEmailResponse(
            email_id=email.id,
            category=EmailCategoryLabel(category_row.category.value),
            confidence=category_row.confidence,
            model_used=category_row.model_used or model_id,
        )

    @staticmethod
    def _coerce_category(value: object) -> EmailCategory:
        try:
            return EmailCategory(str(value).strip().lower())
        except ValueError:
            return EmailCategory.UPDATES

    @staticmethod
    def _coerce_confidence(value: object) -> float:
        try:
            return max(0.0, min(1.0, float(value)))
        except (TypeError, ValueError):
            return 0.5

    async def translate_search_query(
        self,
        db: AsyncSession,
        user: User,
        query: str,
    ) -> TranslateSearchResponse:
        provider_name, model_id = await self._resolve_model(db, user.id)
        provider = self._get_provider(provider_name)

        result = await provider.complete_json(
            model=model_id,
            system_prompt=SEARCH_SYSTEM,
            user_prompt=build_search_prompt(query=query),
        )

        try:
            parsed = json.loads(result.content)
        except json.JSONDecodeError as exc:
            raise AppError("AI returned invalid search format", status_code=502) from exc

        await self._track_usage(
            db,
            user.id,
            AIActionType.SEARCH,
            provider=result.provider,
            model=result.model,
            prompt_tokens=result.prompt_tokens,
            completion_tokens=result.completion_tokens,
            total_tokens=result.total_tokens,
            metadata={"query": query},
        )
        await db.commit()

        return TranslateSearchResponse(
            natural_query=query,
            gmail_query=parsed.get("gmail_query", query),
            explanation=parsed.get("explanation", ""),
            model_used=model_id,
        )
