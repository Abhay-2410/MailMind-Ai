"""Redis snapshots for cleanup/triage job progress (survives brief restarts)."""

from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

JOB_TTL_SECONDS = 60 * 60  # 1 hour


def _key(kind: str, job_id: str) -> str:
    return f"mailmind:job:{kind}:{job_id}"


async def save_job_snapshot(kind: str, job_id: str, payload: dict[str, Any]) -> None:
    try:
        from app.core.redis import get_redis_client

        client = get_redis_client()
        await client.setex(_key(kind, job_id), JOB_TTL_SECONDS, json.dumps(payload, default=str))
    except Exception as exc:  # noqa: BLE001
        logger.debug("Job snapshot save skipped: %s", exc)


async def load_job_snapshot(kind: str, job_id: str) -> dict[str, Any] | None:
    try:
        from app.core.redis import get_redis_client

        client = get_redis_client()
        raw = await client.get(_key(kind, job_id))
        if not raw:
            return None
        data = json.loads(raw)
        return data if isinstance(data, dict) else None
    except Exception as exc:  # noqa: BLE001
        logger.debug("Job snapshot load skipped: %s", exc)
        return None
