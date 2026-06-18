from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request

from app.core.dependencies import get_current_active_user, get_db, get_email_service
from app.middleware.rate_limit import apply_rate_limit
from app.models.category import EmailCategory
from app.models.user import User
from app.schemas.email import (
    EmailListResponse,
    EmailSortField,
    SortOrder,
    SyncInboxRequest,
    SyncInboxResponse,
)
from app.services.email_service import EmailService, categorize_recent_emails_job
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()


@router.get("", response_model=EmailListResponse)
@apply_rate_limit("60/minute")
async def list_inbox(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    is_read: bool | None = Query(None),
    is_important: bool | None = Query(None),
    category: EmailCategory | None = Query(None),
    search: str | None = Query(None, max_length=200),
    sort_by: EmailSortField = Query(EmailSortField.RECEIVED_AT),
    sort_order: SortOrder = Query(SortOrder.DESC),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
    email_service: EmailService = Depends(get_email_service),
) -> EmailListResponse:
    _ = request
    return await email_service.list_emails(
        db,
        current_user,
        page=page,
        page_size=page_size,
        is_read=is_read,
        is_important=is_important,
        category=category,
        search=search,
        sort_by=sort_by,
        sort_order=sort_order,
    )


@router.post("/sync", response_model=SyncInboxResponse)
@apply_rate_limit("10/minute")
async def sync_inbox(
    request: Request,
    body: SyncInboxRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
    email_service: EmailService = Depends(get_email_service),
) -> SyncInboxResponse:
    _ = request
    response = await email_service.sync_inbox(
        db,
        current_user,
        max_results=body.max_results,
        sync_all=body.sync_all,
        query=body.query,
        categorize=False,
    )
    background_tasks.add_task(categorize_recent_emails_job, current_user.id, body.max_results)
    return response
