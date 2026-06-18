from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_active_user, get_db
from app.middleware.rate_limit import apply_rate_limit
from app.models.user import User
from app.schemas.dashboard import DashboardResponse
from app.services.dashboard_service import DashboardService

router = APIRouter()


def get_dashboard_service() -> DashboardService:
    return DashboardService()


@router.get("", response_model=DashboardResponse)
@apply_rate_limit("60/minute")
async def get_dashboard(
    request: Request,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
    dashboard_service: DashboardService = Depends(get_dashboard_service),
) -> DashboardResponse:
    _ = request
    return await dashboard_service.get_dashboard(db, current_user)
