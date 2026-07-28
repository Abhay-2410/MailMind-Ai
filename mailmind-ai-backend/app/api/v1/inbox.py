import asyncio
from datetime import UTC, datetime
from uuid import UUID

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
    SyncStatusResponse,
)
from app.services.email_service import (
    EmailService,
    categorize_recent_emails_job,
    run_full_inbox_sync_job,
    sync_remaining_emails_job,
)
from app.services.sync_jobs import inbox_sync_job_store
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()

_full_sync_tasks: dict[str, asyncio.Task[None]] = {}


def is_full_sync_running(user_id: UUID) -> bool:
    task = _full_sync_tasks.get(str(user_id))
    return task is not None and not task.done()


def _start_full_sync(user_id: UUID) -> None:
    key = str(user_id)
    existing = _full_sync_tasks.get(key)
    if existing and not existing.done():
        return

    async def _run() -> None:
        try:
            await run_full_inbox_sync_job(user_id)
        finally:
            _full_sync_tasks.pop(key, None)

    _full_sync_tasks[key] = asyncio.create_task(_run())


@router.get("", response_model=EmailListResponse)
@apply_rate_limit("60/minute")
async def list_inbox(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    is_read: bool | None = Query(None),
    is_important: bool | None = Query(None),
    has_summary: bool | None = Query(None),
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
        has_summary=has_summary,
        category=category,
        search=search,
        sort_by=sort_by,
        sort_order=sort_order,
    )


@router.get("/sync/status", response_model=SyncStatusResponse)
@apply_rate_limit("120/minute")
async def sync_status(
    request: Request,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
    email_service: EmailService = Depends(get_email_service),
) -> SyncStatusResponse:
    _ = request
    job = inbox_sync_job_store.get(current_user.id)
    account_email: str | None = None
    last_synced_at = None
    try:
        account = await email_service.get_primary_account(db, current_user.id)
        account_email = account.email
        last_synced_at = account.last_synced_at
    except Exception:
        pass

    if job is None:
        return SyncStatusResponse(
            status="idle",
            phase="idle",
            last_synced_at=last_synced_at,
            account_email=account_email,
        )

    async with job.lock:
        status = job.status
        phase = job.phase
        error = job.error
        if status == "running" and not is_full_sync_running(current_user.id):
            status = "failed"
            phase = "failed"
            error = error or "Sync interrupted — server restarted. Please sync again."
            job.status = status
            job.phase = phase
            job.error = error
            job.finished_at = job.finished_at or datetime.now(UTC)

        return SyncStatusResponse(
            status=status,
            phase=phase,
            listed_count=job.listed_count,
            fetched_count=job.fetched_count,
            new_count=job.new_count,
            updated_count=job.updated_count,
            error=error,
            last_synced_at=last_synced_at,
            account_email=account_email,
        )


@router.post("/sync", response_model=SyncInboxResponse)
@apply_rate_limit("30/minute")
async def sync_inbox(
    request: Request,
    body: SyncInboxRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
    email_service: EmailService = Depends(get_email_service),
) -> SyncInboxResponse:
    _ = request

    if body.sync_all:
        existing_job = inbox_sync_job_store.get(current_user.id)
        if existing_job is None or existing_job.status != "running":
            await inbox_sync_job_store.start(current_user.id)
            _start_full_sync(current_user.id)

        job = inbox_sync_job_store.get(current_user.id)
        account = await email_service.get_primary_account(db, current_user.id)
        return SyncInboxResponse(
            synced_count=job.listed_count if job else 0,
            new_count=job.new_count if job else 0,
            updated_count=job.updated_count if job else 0,
            account_email=account.email,
            last_synced_at=account.last_synced_at,
            background=True,
            status=job.status if job else "running",
        )

    response, deferred_ids = await email_service.sync_inbox(
        db,
        current_user,
        max_results=body.max_results,
        sync_all=False,
        incremental=body.incremental,
        query=body.query,
        categorize=False,
    )
    if deferred_ids:
        background_tasks.add_task(sync_remaining_emails_job, current_user.id, deferred_ids)
    background_tasks.add_task(categorize_recent_emails_job, current_user.id, 2000)
    return response
