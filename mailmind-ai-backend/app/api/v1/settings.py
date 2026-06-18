from fastapi import APIRouter, Depends, Request

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_active_user, get_db
from app.middleware.rate_limit import apply_rate_limit
from app.models.user import User
from app.schemas.settings import AccountSummary, SettingsResponse, UpdateSettingsRequest
from app.services.settings_service import SettingsService

router = APIRouter()


def get_settings_service() -> SettingsService:
    return SettingsService()


@router.get("", response_model=SettingsResponse)
@apply_rate_limit("60/minute")
async def get_settings(
    request: Request,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
    settings_service: SettingsService = Depends(get_settings_service),
) -> SettingsResponse:
    _ = request
    return await settings_service.get_settings(db, current_user)


@router.patch("", response_model=SettingsResponse)
@apply_rate_limit("30/minute")
async def update_settings(
    request: Request,
    body: UpdateSettingsRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
    settings_service: SettingsService = Depends(get_settings_service),
) -> SettingsResponse:
    _ = request
    return await settings_service.update_settings(db, current_user, body)


@router.get("/accounts", response_model=list[AccountSummary])
@apply_rate_limit("60/minute")
async def list_accounts(
    request: Request,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
    settings_service: SettingsService = Depends(get_settings_service),
) -> list[AccountSummary]:
    _ = request
    return await settings_service.list_accounts(db, current_user.id)
