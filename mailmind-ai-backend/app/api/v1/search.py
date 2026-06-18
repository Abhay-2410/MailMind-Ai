from fastapi import APIRouter, Depends, Query, Request

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_active_user, get_db
from app.middleware.rate_limit import apply_rate_limit
from app.models.user import User
from app.schemas.search import SearchHistoryItem, SearchRequest, SearchResponse
from app.services.search_service import SearchService

router = APIRouter()


def get_search_service() -> SearchService:
    return SearchService()


@router.post("", response_model=SearchResponse)
@apply_rate_limit("20/minute")
async def execute_search(
    request: Request,
    body: SearchRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
    search_service: SearchService = Depends(get_search_service),
) -> SearchResponse:
    _ = request
    return await search_service.search(
        db,
        current_user,
        query=body.query,
        max_results=body.max_results,
    )


@router.get("/history", response_model=list[SearchHistoryItem])
@apply_rate_limit("60/minute")
async def get_search_history(
    request: Request,
    limit: int = Query(10, ge=1, le=50),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
    search_service: SearchService = Depends(get_search_service),
) -> list[SearchHistoryItem]:
    _ = request
    return await search_service.list_history(db, current_user, limit=limit)
