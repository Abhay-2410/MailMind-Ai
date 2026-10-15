import hmac

from fastapi import APIRouter, Header

from app.core.config import get_settings
from app.core.exceptions import AppError
from app.services.background_sync import run_scheduled_sync

router = APIRouter()

CRON_SYNC_BUDGET_SECONDS = 240


@router.get("/sync", include_in_schema=False)
async def cron_sync(authorization: str | None = Header(None)) -> dict[str, int]:
    """Vercel Cron entry point; Vercel sends ``Authorization: Bearer $CRON_SECRET``."""
    secret = get_settings().CRON_SECRET
    if not secret or not hmac.compare_digest(authorization or "", f"Bearer {secret}"):
        raise AppError("Unauthorized", status_code=401)
    return await run_scheduled_sync(CRON_SYNC_BUDGET_SECONDS)
