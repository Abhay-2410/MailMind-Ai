from fastapi import APIRouter, BackgroundTasks, Depends, Request, Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db
from app.core.exceptions import AppError
from app.models.account import Account
from app.services.email_service import run_incremental_sync_job
from app.services.gmail_push_service import decode_push_payload, push_enabled, verify_push_token

router = APIRouter()


@router.post("/push", status_code=204)
async def gmail_push(
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Pub/Sub push endpoint: Gmail reports a mailbox change, we run an incremental sync."""
    if not push_enabled():
        raise AppError("Gmail push is not configured", status_code=404)

    await verify_push_token(request.headers.get("Authorization"))
    try:
        body = await request.json()
    except ValueError as exc:
        raise AppError("Invalid push body", status_code=400) from exc
    email_address, _history_id = decode_push_payload(body if isinstance(body, dict) else {})

    result = await db.execute(
        select(Account.user_id).where(
            func.lower(Account.email) == email_address,
            Account.is_active.is_(True),
        )
    )
    for user_id in {row[0] for row in result.all()}:
        background_tasks.add_task(run_incremental_sync_job, user_id)
    # Always acknowledge so Pub/Sub does not redeliver for unknown mailboxes.
    return Response(status_code=204)
