"""Inbox sync job tracking: in-memory for the live process, mirrored to Redis so
progress survives a restart and interrupted full syncs can be resumed."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from app.services.job_progress_redis import list_job_snapshots, load_job_snapshot, save_job_snapshot

SNAPSHOT_KIND = "inbox_sync"
# Long enough that last_completed_at survives between daily reconciles.
SNAPSHOT_TTL_SECONDS = 7 * 24 * 60 * 60
# How often a full re-list runs once the mailbox is in sync (history covers the rest).
FULL_RECONCILE_INTERVAL = timedelta(hours=24)
RECONCILE_RETRY_AFTER = timedelta(minutes=30)
# A running job whose heartbeat is older than this lost its driver (killed instance/tab).
STALE_RUNNING_AFTER = timedelta(minutes=10)


def _shared_state() -> bool:
    from app.core.config import get_settings

    return get_settings().is_serverless


@dataclass
class InboxSyncJob:
    user_id: UUID
    status: str = "idle"  # idle | running | completed | failed
    phase: str = "idle"  # idle | syncing | categorizing | failed
    # full: user-visible first/explicit sync; reconcile: quiet background re-list.
    mode: str = "full"
    listed_count: int = 0
    fetched_count: int = 0
    new_count: int = 0
    updated_count: int = 0
    error: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    last_completed_at: datetime | None = None
    heartbeat_at: datetime | None = None
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    def is_stale(self, now: datetime | None = None) -> bool:
        beat = self.heartbeat_at or self.started_at
        return beat is None or (now or datetime.now(UTC)) - beat > STALE_RUNNING_AFTER

    def reconcile_due(self, now: datetime | None = None) -> bool:
        now = now or datetime.now(UTC)
        if (
            self.status == "failed"
            and self.finished_at is not None
            and now - self.finished_at < RECONCILE_RETRY_AFTER
        ):
            return False
        if self.last_completed_at is None:
            return True
        return now - self.last_completed_at >= FULL_RECONCILE_INTERVAL

    def snapshot(self) -> dict[str, Any]:
        return {
            "user_id": str(self.user_id),
            "status": self.status,
            "phase": self.phase,
            "mode": self.mode,
            "listed_count": self.listed_count,
            "fetched_count": self.fetched_count,
            "new_count": self.new_count,
            "updated_count": self.updated_count,
            "error": self.error,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "last_completed_at": self.last_completed_at.isoformat() if self.last_completed_at else None,
            "heartbeat_at": self.heartbeat_at.isoformat() if self.heartbeat_at else None,
        }

    @classmethod
    def from_snapshot(cls, data: dict[str, Any]) -> InboxSyncJob:
        def _dt(value: Any) -> datetime | None:
            try:
                return datetime.fromisoformat(value) if value else None
            except (TypeError, ValueError):
                return None

        return cls(
            user_id=UUID(str(data["user_id"])),
            status=str(data.get("status") or "idle"),
            phase=str(data.get("phase") or "idle"),
            mode=str(data.get("mode") or "full"),
            listed_count=int(data.get("listed_count") or 0),
            fetched_count=int(data.get("fetched_count") or 0),
            new_count=int(data.get("new_count") or 0),
            updated_count=int(data.get("updated_count") or 0),
            error=data.get("error"),
            started_at=_dt(data.get("started_at")),
            finished_at=_dt(data.get("finished_at")),
            last_completed_at=_dt(data.get("last_completed_at")),
            heartbeat_at=_dt(data.get("heartbeat_at")),
        )


class InboxSyncJobStore:
    def __init__(self) -> None:
        self._jobs: dict[str, InboxSyncJob] = {}

    def get(self, user_id: UUID) -> InboxSyncJob | None:
        return self._jobs.get(str(user_id))

    async def load(self, user_id: UUID) -> InboxSyncJob | None:
        """In-memory job, else the last snapshot persisted by a previous process.

        Serverless instances don't share memory, so there Redis is always authoritative.
        """
        job = self.get(user_id)
        if job is not None and not _shared_state():
            return job
        data = await load_job_snapshot(SNAPSHOT_KIND, str(user_id))
        if data is None:
            return job
        try:
            job = InboxSyncJob.from_snapshot(data)
        except (KeyError, ValueError):
            return None
        self._jobs[str(user_id)] = job
        return job

    async def interrupted_jobs(self) -> list[tuple[UUID, str]]:
        """(user id, mode) of full syncs still running when the previous process stopped."""
        jobs: list[tuple[UUID, str]] = []
        for data in await list_job_snapshots(SNAPSHOT_KIND):
            if data.get("status") != "running":
                continue
            try:
                jobs.append((UUID(str(data["user_id"])), str(data.get("mode") or "full")))
            except (KeyError, ValueError):
                continue
        return jobs

    def get_or_create(self, user_id: UUID) -> InboxSyncJob:
        key = str(user_id)
        job = self._jobs.get(key)
        if job is None:
            job = InboxSyncJob(user_id=user_id)
            self._jobs[key] = job
        return job

    async def _persist(self, job: InboxSyncJob) -> None:
        job.heartbeat_at = datetime.now(UTC)
        await save_job_snapshot(
            SNAPSHOT_KIND,
            str(job.user_id),
            job.snapshot(),
            ttl_seconds=SNAPSHOT_TTL_SECONDS,
        )

    async def start(self, user_id: UUID, *, mode: str = "full") -> InboxSyncJob:
        job = await self.load(user_id) or self.get_or_create(user_id)
        async with job.lock:
            job.status = "running"
            job.phase = "syncing"
            job.mode = mode
            job.listed_count = 0
            job.fetched_count = 0
            job.new_count = 0
            job.updated_count = 0
            job.error = None
            job.started_at = datetime.now(UTC)
            job.finished_at = None
        await self._persist(job)
        return job

    async def update(
        self,
        job: InboxSyncJob,
        *,
        listed_count: int | None = None,
        fetched_count: int | None = None,
        new_count: int | None = None,
        updated_count: int | None = None,
        phase: str | None = None,
    ) -> None:
        async with job.lock:
            if listed_count is not None:
                job.listed_count = listed_count
            if fetched_count is not None:
                job.fetched_count = fetched_count
            if new_count is not None:
                job.new_count = new_count
            if updated_count is not None:
                job.updated_count = updated_count
            if phase is not None:
                job.phase = phase
        await self._persist(job)

    async def complete(self, job: InboxSyncJob) -> None:
        async with job.lock:
            job.status = "completed"
            job.phase = "idle"
            job.finished_at = datetime.now(UTC)
            job.last_completed_at = job.finished_at
        await self._persist(job)

    async def fail(self, job: InboxSyncJob, error: str) -> None:
        async with job.lock:
            job.status = "failed"
            job.phase = "failed"
            job.error = error
            job.finished_at = datetime.now(UTC)
        await self._persist(job)


inbox_sync_job_store = InboxSyncJobStore()
