import asyncio
import logging
import time
from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.background import spawn
from app.core.config import get_settings
from app.core.dependencies import get_current_active_user, get_db, get_email_service
from app.core.exceptions import AppError, GmailReauthRequired
from app.middleware.rate_limit import apply_rate_limit
from app.models.category import EmailCategory
from app.models.email import Email
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
    AI_CATEGORIZE_AFTER_FULL_SYNC,
    AI_CATEGORIZE_AFTER_INCREMENTAL,
    INCREMENTAL_SYNC_TIMEOUT_SECONDS,
    EmailService,
    categorize_recent_emails_job,
    incremental_sync_lock,
    run_full_inbox_sync_job,
    sync_remaining_emails_job,
)
from app.services.background_sync import reset_background_backoff
from app.services.sync_jobs import inbox_sync_job_store

logger = logging.getLogger(__name__)

router = APIRouter()

_full_sync_tasks: dict[str, asyncio.Task[None]] = {}
_gmail_total_refreshes: dict[UUID, asyncio.Task[None]] = {}
GMAIL_TOTAL_CACHE_SECONDS = 120
GMAIL_TOTAL_TIMEOUT_SECONDS = 20
# One drive step must finish well inside the 300s function limit.
DRIVE_STEP_SECONDS = 200
DRIVE_LEASE_SECONDS = DRIVE_STEP_SECONDS + 60


def is_full_sync_running(user_id: UUID) -> bool:
    task = _full_sync_tasks.get(str(user_id))
    return task is not None and not task.done()


def _client_driven() -> bool:
    """On serverless there is no long-lived process: the open app advances full syncs
    through POST /inbox/sync/drive, one time-boxed step per call."""
    return get_settings().is_serverless


async def full_sync_active(user_id: UUID) -> bool:
    if not _client_driven():
        return is_full_sync_running(user_id)
    job = await inbox_sync_job_store.load(user_id)
    return job is not None and job.status == "running" and not job.is_stale(datetime.now(UTC))


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


async def start_full_sync_job(user_id: UUID, *, mode: str = "full") -> None:
    if await full_sync_active(user_id):
        return
    await inbox_sync_job_store.start(user_id, mode=mode)
    if not _client_driven():
        _start_full_sync(user_id)


async def resume_interrupted_syncs() -> int:
    """Restart full syncs that were running when the previous process stopped.

    Safe to resume from scratch: already-stored, up-to-date emails are skipped.
    """
    jobs = await inbox_sync_job_store.interrupted_jobs()
    for user_id, mode in jobs:
        await start_full_sync_job(user_id, mode=mode)
    if jobs:
        logger.info("Resumed %s interrupted inbox sync job(s)", len(jobs))
    return len(jobs)


def _gmail_total_cache_key(account_id: UUID) -> str:
    return f"mailmind:gmail_total:{account_id}"


async def _cached_gmail_total(account_id: UUID) -> int | None:
    try:
        from app.core.redis import get_redis_client

        cached = await get_redis_client().get(_gmail_total_cache_key(account_id))
    except Exception:  # noqa: BLE001
        return None
    return int(cached) if cached is not None else None


def _schedule_gmail_total_refresh(user_id: UUID) -> None:
    """Refresh the cached Gmail total off the request path; status polls never wait on Gmail."""
    existing = _gmail_total_refreshes.get(user_id)
    if existing is not None and not existing.done():
        return

    async def _refresh() -> None:
        from app.core.redis import get_redis_client
        from app.db.session import AsyncSessionLocal

        try:
            async with asyncio.timeout(GMAIL_TOTAL_TIMEOUT_SECONDS), AsyncSessionLocal() as db:
                service = EmailService()
                account = await service.get_primary_account(db, user_id)
                total = await service.gmail.get_syncable_message_total(account=account, db=db)
                await get_redis_client().setex(
                    _gmail_total_cache_key(account.id), GMAIL_TOTAL_CACHE_SECONDS, str(total)
                )
        except Exception as exc:  # noqa: BLE001
            logger.debug("Gmail total refresh failed for %s: %r", user_id, exc)
        finally:
            _gmail_total_refreshes.pop(user_id, None)

    _gmail_total_refreshes[user_id] = spawn(_refresh())


@router.get("", response_model=EmailListResponse)
@apply_rate_limit("60/minute")
async def list_inbox(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    is_read: bool | None = Query(None),
    is_important: bool | None = Query(None),
    is_priority: bool | None = Query(None),
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
        is_priority=is_priority,
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
    return await _build_sync_status(current_user, db, email_service)


@router.post("/sync/drive", response_model=SyncStatusResponse)
@apply_rate_limit("30/minute")
async def drive_sync(
    request: Request,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
    email_service: EmailService = Depends(get_email_service),
) -> SyncStatusResponse:
    """Advance a running full sync by one time-boxed step (serverless only).

    A Redis lease keeps concurrent tabs from driving the same mailbox twice; a caller
    that loses the race just gets the current status back.
    """
    _ = request
    user_id = current_user.id
    job = await inbox_sync_job_store.load(user_id)
    if _client_driven() and job is not None and job.status == "running":
        from app.core.redis import get_redis_client

        redis = get_redis_client()
        lease_key = f"mailmind:sync_drive:{user_id}"
        if await redis.set(lease_key, "1", nx=True, ex=DRIVE_LEASE_SECONDS):
            # Release the request's pooled connection while Gmail is being read.
            await db.commit()
            try:
                outcome = await run_full_inbox_sync_job(
                    user_id,
                    deadline=time.monotonic() + DRIVE_STEP_SECONDS,
                    categorize_after=False,
                )
            finally:
                await redis.delete(lease_key)
            if outcome == "completed":
                spawn(categorize_recent_emails_job(user_id, AI_CATEGORIZE_AFTER_FULL_SYNC))
    return await _build_sync_status(current_user, db, email_service)


async def _build_sync_status(
    current_user: User, db: AsyncSession, email_service: EmailService
) -> SyncStatusResponse:
    job = await inbox_sync_job_store.load(current_user.id)
    driver = "client" if _client_driven() else "server"
    account_email: str | None = None
    last_synced_at = None
    gmail_total: int | None = None
    stored_count: int | None = None
    needs_reconnect = False
    try:
        account = await email_service.get_primary_account(db, current_user.id)
        account_email = account.email
        last_synced_at = account.last_synced_at
        needs_reconnect = not account.refresh_token_encrypted
        stored_count = await db.scalar(
            select(func.count(Email.id)).where(Email.account_id == account.id)
        )
        gmail_total = await _cached_gmail_total(account.id)
        if gmail_total is None and not needs_reconnect:
            _schedule_gmail_total_refresh(current_user.id)
    except AppError:
        pass

    if job is None:
        return SyncStatusResponse(
            status="idle",
            phase="idle",
            last_synced_at=last_synced_at,
            account_email=account_email,
            gmail_total=gmail_total,
            stored_count=stored_count,
            needs_reconnect=needs_reconnect,
            driver=driver,
        )

    async with job.lock:
        status = job.status
        phase = job.phase
        error = job.error
        if status == "running" and not _client_driven() and not is_full_sync_running(current_user.id):
            status = "failed"
            phase = "failed"
            error = error or "Sync interrupted. Please sync again."
            job.status = status
            job.phase = phase
            job.error = error
            job.finished_at = job.finished_at or datetime.now(UTC)

        return SyncStatusResponse(
            status=status,
            phase=phase,
            mode=job.mode,
            listed_count=job.listed_count,
            fetched_count=job.fetched_count,
            new_count=job.new_count,
            updated_count=job.updated_count,
            error=error,
            last_synced_at=last_synced_at,
            last_full_sync_at=job.last_completed_at,
            account_email=account_email,
            gmail_total=gmail_total,
            stored_count=stored_count,
            needs_reconnect=needs_reconnect,
            driver=driver,
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
    reset_background_backoff(current_user.id)
    incremental = body.incremental

    if body.sync_all:
        incremental = False
        account = await email_service.get_primary_account(db, current_user.id)
        if not account.refresh_token_encrypted:
            raise GmailReauthRequired()
        job = await inbox_sync_job_store.load(current_user.id)
        in_sync = bool(
            account.gmail_history_id
            and account.last_synced_at
            and job is not None
            and job.last_completed_at is not None
        )
        if await full_sync_active(current_user.id):
            pass
        elif body.auto and in_sync and job is not None:
            # Already mirrored: history-based sync is enough; re-list quietly once a day.
            if job.reconcile_due():
                await start_full_sync_job(current_user.id, mode="reconcile")
            else:
                incremental = True
        else:
            await start_full_sync_job(current_user.id, mode="full")

        if not incremental:
            job = await inbox_sync_job_store.load(current_user.id)
            return SyncInboxResponse(
                synced_count=job.listed_count if job else 0,
                new_count=job.new_count if job else 0,
                updated_count=job.updated_count if job else 0,
                account_email=account.email,
                last_synced_at=account.last_synced_at,
                background=True,
                status=job.status if job else "running",
            )

    lock = incremental_sync_lock(current_user.id)
    if incremental and not body.query and lock.locked():
        # The background loop (or a push) is already syncing this mailbox.
        account = await email_service.get_primary_account(db, current_user.id)
        return SyncInboxResponse(
            synced_count=0,
            new_count=0,
            updated_count=0,
            account_email=account.email,
            last_synced_at=account.last_synced_at,
            status="running",
        )

    try:
        async with lock, asyncio.timeout(INCREMENTAL_SYNC_TIMEOUT_SECONDS):
            response, deferred_ids = await email_service.sync_inbox(
                db,
                current_user,
                max_results=body.max_results,
                sync_all=False,
                incremental=incremental,
                query=body.query,
            )
    except TimeoutError as exc:
        raise AppError("Gmail is responding slowly — sync will retry automatically", status_code=504) from exc
    if deferred_ids:
        background_tasks.add_task(sync_remaining_emails_job, current_user.id, deferred_ids)
    if response.new_count:
        background_tasks.add_task(
            categorize_recent_emails_job, current_user.id, AI_CATEGORIZE_AFTER_INCREMENTAL
        )
    return response
