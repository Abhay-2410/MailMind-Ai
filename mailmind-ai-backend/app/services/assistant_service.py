from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.prompts.assistant import ASSISTANT_SYSTEM, build_assistant_prompt
from app.models.ai_usage import AIActionType
from app.models.email import Email
from app.models.user import User
from app.schemas.ai import AssistantResponse
from app.services.ai_service import AIService

ASSISTANT_MAX_TOKENS = 256


class AssistantService(AIService):
    async def ask(
        self,
        db: AsyncSession,
        user: User,
        question: str,
    ) -> AssistantResponse:
        result = await db.execute(
            select(Email)
            .where(Email.user_id == user.id)
            .order_by(Email.received_at.desc())
            .limit(20)
        )
        emails = result.scalars().all()

        context_lines = []
        for email in emails:
            context_lines.append(
                f"- [{email.received_at.date()}] From: {email.sender} | "
                f"Subject: {email.subject} | Read: {email.is_read} | "
                f"Preview: {(email.preview or '')[:200]}"
            )

        context = "\n".join(context_lines) if context_lines else "No emails synced yet."
        provider_name, model_id = await self._resolve_model(db, user.id)
        provider = self._get_provider(provider_name)

        completion = await provider.complete(
            model=model_id,
            system_prompt=ASSISTANT_SYSTEM,
            user_prompt=build_assistant_prompt(question=question, context=context),
            temperature=0.3,
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
            metadata={"question": question[:200]},
        )
        await db.commit()

        return AssistantResponse(answer=completion.content, model_used=model_id)
