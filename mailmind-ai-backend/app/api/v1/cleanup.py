from fastapi import APIRouter, Depends, Request

from app.core.dependencies import get_current_active_user, get_db
from app.middleware.rate_limit import apply_rate_limit
from app.models.user import User
from app.schemas.cleanup import (
    CleanupAnalyzeProgressResponse,
    CleanupAnalyzeRequest,
    CleanupAnalyzeResponse,
    CleanupCountsResponse,
    CleanupDeleteRequest,
    CleanupDeleteResponse,
    CleanupRestoreRequest,
    CleanupRestoreResponse,
    TriageAnalyzeProgressResponse,
    TriageAnalyzeRequest,
    TriageAnalyzeResponse,
    TriageDeleteRequest,
    TriageDeleteResponse,
)
from app.services.cleanup_service import CleanupService
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()


def get_cleanup_service() -> CleanupService:
    return CleanupService()


@router.get("/counts", response_model=CleanupCountsResponse)
@apply_rate_limit("20/minute")
async def get_cleanup_counts(
    request: Request,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
    cleanup_service: CleanupService = Depends(get_cleanup_service),
) -> CleanupCountsResponse:
    _ = request
    return await cleanup_service.get_counts(db, current_user)


@router.post("/analyze", response_model=CleanupAnalyzeProgressResponse)
@apply_rate_limit("10/minute")
async def start_cleanup_analyze(
    request: Request,
    payload: CleanupAnalyzeRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
    cleanup_service: CleanupService = Depends(get_cleanup_service),
) -> CleanupAnalyzeProgressResponse:
    _ = request
    return await cleanup_service.start_analyze_job(db, current_user, payload)


@router.get("/analyze/{job_id}", response_model=CleanupAnalyzeProgressResponse)
@apply_rate_limit("60/minute")
async def get_cleanup_analyze_progress(
    request: Request,
    job_id: str,
    current_user: User = Depends(get_current_active_user),
    cleanup_service: CleanupService = Depends(get_cleanup_service),
) -> CleanupAnalyzeProgressResponse:
    _ = request
    return await cleanup_service.get_analyze_progress(job_id, current_user)


@router.post("/analyze/sync", response_model=CleanupAnalyzeResponse)
@apply_rate_limit("5/minute")
async def analyze_cleanup_sync(
    request: Request,
    payload: CleanupAnalyzeRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
    cleanup_service: CleanupService = Depends(get_cleanup_service),
) -> CleanupAnalyzeResponse:
    """Synchronous analyze for small categories or tests."""
    _ = request
    return await cleanup_service.analyze(db, current_user, payload)


@router.post("/delete", response_model=CleanupDeleteResponse)
@apply_rate_limit("10/minute")
async def delete_cleanup_messages(
    request: Request,
    payload: CleanupDeleteRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
    cleanup_service: CleanupService = Depends(get_cleanup_service),
) -> CleanupDeleteResponse:
    _ = request
    return await cleanup_service.delete_messages(db, current_user, payload)


@router.post("/restore", response_model=CleanupRestoreResponse)
@apply_rate_limit("10/minute")
async def restore_cleanup_messages(
    request: Request,
    payload: CleanupRestoreRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
    cleanup_service: CleanupService = Depends(get_cleanup_service),
) -> CleanupRestoreResponse:
    _ = request
    return await cleanup_service.restore_messages(db, current_user, payload)


@router.post("/triage/analyze", response_model=TriageAnalyzeProgressResponse)
@apply_rate_limit("5/minute")
async def start_triage_analyze(
    request: Request,
    payload: TriageAnalyzeRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
    cleanup_service: CleanupService = Depends(get_cleanup_service),
) -> TriageAnalyzeProgressResponse:
    _ = request
    return await cleanup_service.start_triage_analyze_job(db, current_user, payload)


@router.get("/triage/analyze/{job_id}", response_model=TriageAnalyzeProgressResponse)
@apply_rate_limit("60/minute")
async def get_triage_analyze_progress(
    request: Request,
    job_id: str,
    current_user: User = Depends(get_current_active_user),
    cleanup_service: CleanupService = Depends(get_cleanup_service),
) -> TriageAnalyzeProgressResponse:
    _ = request
    return await cleanup_service.get_triage_analyze_progress(job_id, current_user)


@router.post("/triage/delete", response_model=TriageDeleteResponse)
@apply_rate_limit("10/minute")
async def delete_triage_tier(
    request: Request,
    payload: TriageDeleteRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
    cleanup_service: CleanupService = Depends(get_cleanup_service),
) -> TriageDeleteResponse:
    _ = request
    return await cleanup_service.delete_triage_tier(db, current_user, payload)
