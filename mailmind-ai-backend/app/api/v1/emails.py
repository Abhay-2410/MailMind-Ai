from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.dependencies import get_current_active_user, get_db, get_email_service
from app.middleware.rate_limit import apply_rate_limit
from app.models.category import EmailCategory
from app.models.email import Email
from app.models.user import User
from app.schemas.email import EmailDetail, UpdateEmailCategoryRequest, UpdateEmailCategoryResponse
from app.services.categorization_service import CategorizationService
from app.services.email_service import EmailService

router = APIRouter()


@router.get("/{email_id}", response_model=EmailDetail)
@apply_rate_limit("60/minute")
async def get_email(
    request: Request,
    email_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
    email_service: EmailService = Depends(get_email_service),
) -> EmailDetail:
    _ = request
    return await email_service.get_email(db, current_user, email_id)


@router.patch("/{email_id}/category", response_model=UpdateEmailCategoryResponse)
@apply_rate_limit("60/minute")
async def update_email_category(
    request: Request,
    email_id: UUID,
    body: UpdateEmailCategoryRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
    email_service: EmailService = Depends(get_email_service),
) -> UpdateEmailCategoryResponse:
    """User correction: pins this email (and by default every email from the sender)."""
    _ = request
    email, updated = await CategorizationService().set_user_category(
        db,
        current_user,
        email_id,
        EmailCategory(body.category.value),
        apply_to_sender=body.apply_to_sender,
    )
    result = await db.execute(
        select(Email)
        .where(Email.id == email.id)
        .options(selectinload(Email.category), selectinload(Email.summary))
        .execution_options(populate_existing=True)
    )
    refreshed = result.scalar_one()
    return UpdateEmailCategoryResponse(
        email=email_service._to_list_item(refreshed),
        sender_emails_updated=updated,
    )
