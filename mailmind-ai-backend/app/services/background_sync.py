"""Server-side polling so new Gmail mail is stored even when no browser tab is open.

Each tick runs a History API incremental sync (2 quota units when nothing changed)
for every active primary account. Accounts that keep failing (e.g. revoked access)
back off exponentially instead of erroring every tick.
"""

import asyncio
import logging
import time
from uuid import UUID

from sqlalchemy import select

from app.core.config import get_settings
from app.models.account import Account

logger = logging.getLogger(__name__)

MAX_BACKOFF_SECONDS = 30 * 60

_task: asyncio.Task[None] | None = None
_failures: dict[UUID, int] = {}
_retry_at: dict[UUID, float] = {}


def reset_background_backoff(user_id: UUID) -> None:
    """Called on user-initiated syncs (e.g. right after re-connecting Gmail)."""
    _failures.pop(user_id, None)
    _retry_at.pop(user_id, None)


async def _active_user_ids() -> list[UUID]:
    from app.db.session import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Account.user_id).where(
                Account.is_primary.is_(True),
                Account.is_active.is_(True),
                # No refresh token = Google revoked the grant; wait for the user to reconnect.
                Account.refresh_token_encrypted.is_not(None),
                Account.gmail_history_id.is_not(None),
            )
        )
        return list(dict.fromkeys(result.scalars().all()))


async def _sync_user(user_id: UUID, interval: float) -> None:
    from app.api.v1.inbox import is_full_sync_running, start_full_sync_job
    from app.services.email_service import run_incremental_sync_job
    from app.services.sync_jobs import inbox_sync_job_store

    if is_full_sync_running(user_id) or time.monotonic() < _retry_at.get(user_id, 0.0):
        return
    job = await inbox_sync_job_store.load(user_id)
    if job is not None and job.last_completed_at is not None and job.reconcile_due():
        await start_full_sync_job(user_id, mode="reconcile")
        return
    if await run_incremental_sync_job(user_id):
        _failures.pop(user_id, None)
        _retry_at.pop(user_id, None)
        return
    failures = _failures.get(user_id, 0) + 1
    _failures[user_id] = failures
    delay = min(interval * 2**failures, MAX_BACKOFF_SECONDS)
    _retry_at[user_id] = time.monotonic() + delay
    logger.info("Background sync for user %s backing off %.0fs after %s failure(s)", user_id, delay, failures)


async def run_scheduled_sync(budget_seconds: float) -> dict[str, int]:
    """One polling pass for Vercel Cron (serverless has no long-lived loop)."""
    from app.services.email_service import run_incremental_sync_job

    deadline = time.monotonic() + budget_seconds
    counts = {"synced": 0, "failed": 0, "skipped": 0}
    for user_id in await _active_user_ids():
        if time.monotonic() >= deadline:
            counts["skipped"] += 1
        elif await run_incremental_sync_job(user_id):
            counts["synced"] += 1
        else:
            counts["failed"] += 1
    return counts


async def _loop(interval: float) -> None:
    logger.info("Background Gmail sync every %.0fs", interval)
    while True:
        try:
            for user_id in await _active_user_ids():
                await _sync_user(user_id, interval)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001
            logger.warning("Background Gmail sync tick failed: %s", exc)
        await asyncio.sleep(interval)


def start_background_sync() -> None:
    global _task
    interval = get_settings().BACKGROUND_SYNC_INTERVAL_SECONDS
    if interval <= 0 or (_task is not None and not _task.done()):
        return
    _task = asyncio.create_task(_loop(float(interval)))


async def stop_background_sync() -> None:
    global _task
    if _task is None:
        return
    _task.cancel()
    try:
        await _task
    except asyncio.CancelledError:
        pass
    _task = None
