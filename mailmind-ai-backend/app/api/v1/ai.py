from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_active_user, get_db
from app.middleware.rate_limit import apply_rate_limit
from app.models.user import User
from app.schemas.ai import (
    AIModelResponse,
    AssistantRequest,
    AssistantResponse,
    CategorizeEmailRequest,
    CategorizeEmailResponse,
    GenerateReplyRequest,
    GenerateReplyResponse,
    SummarizeEmailRequest,
    SummarizeEmailResponse,
    TranslateSearchRequest,
    TranslateSearchResponse,
)
from app.services.ai_service import AIService
from app.services.assistant_service import AssistantService

router = APIRouter()


def get_ai_service() -> AIService:
    return AIService()


def get_assistant_service() -> AssistantService:
    return AssistantService()


@router.get("/models", response_model=list[AIModelResponse])
@apply_rate_limit("60/minute")
async def list_models(
    request: Request,
    ai_service: AIService = Depends(get_ai_service),
) -> list[AIModelResponse]:
    _ = request
    return await ai_service.list_models()


@router.post("/summarize", response_model=SummarizeEmailResponse)
@apply_rate_limit("30/minute")
async def summarize_email(
    request: Request,
    body: SummarizeEmailRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
    ai_service: AIService = Depends(get_ai_service),
) -> SummarizeEmailResponse:
    _ = request
    return await ai_service.summarize_email(db, current_user, body.email_id)


@router.post("/reply", response_model=GenerateReplyResponse)
@apply_rate_limit("30/minute")
async def generate_reply(
    request: Request,
    body: GenerateReplyRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
    ai_service: AIService = Depends(get_ai_service),
) -> GenerateReplyResponse:
    _ = request
    return await ai_service.generate_reply(
        db,
        current_user,
        body.email_id,
        body.style.value,
    )


@router.post("/categorize", response_model=CategorizeEmailResponse)
@apply_rate_limit("30/minute")
async def categorize_email(
    request: Request,
    body: CategorizeEmailRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
    ai_service: AIService = Depends(get_ai_service),
) -> CategorizeEmailResponse:
    _ = request
    return await ai_service.categorize_email(db, current_user, body.email_id)


@router.post("/search/translate", response_model=TranslateSearchResponse)
@apply_rate_limit("30/minute")
async def translate_search(
    request: Request,
    body: TranslateSearchRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
    ai_service: AIService = Depends(get_ai_service),
) -> TranslateSearchResponse:
    _ = request
    return await ai_service.translate_search_query(db, current_user, body.query)


@router.post("/assistant", response_model=AssistantResponse)
@apply_rate_limit("20/minute")
async def ask_assistant(
    request: Request,
    body: AssistantRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
    assistant_service: AssistantService = Depends(get_assistant_service),
) -> AssistantResponse:
    _ = request
    return await assistant_service.ask(db, current_user, body.question)
