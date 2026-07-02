"""In-memory inbox sync job tracking (development / single-process)."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID


@dataclass
class InboxSyncJob:
    user_id: UUID
    status: str = "idle"  # idle | running | completed | failed
    listed_count: int = 0
    fetched_count: int = 0
    new_count: int = 0
    updated_count: int = 0
    error: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)


class InboxSyncJobStore:
    def __init__(self) -> None:
        self._jobs: dict[str, InboxSyncJob] = {}

    def get(self, user_id: UUID) -> InboxSyncJob | None:
        return self._jobs.get(str(user_id))

    def get_or_create(self, user_id: UUID) -> InboxSyncJob:
        key = str(user_id)
        job = self._jobs.get(key)
        if job is None:
            job = InboxSyncJob(user_id=user_id)
            self._jobs[key] = job
        return job

    async def start(self, user_id: UUID) -> InboxSyncJob:
        job = self.get_or_create(user_id)
        async with job.lock:
            job.status = "running"
            job.listed_count = 0
            job.fetched_count = 0
            job.new_count = 0
            job.updated_count = 0
            job.error = None
            job.started_at = datetime.now(UTC)
            job.finished_at = None
        return job

    async def update(
        self,
        job: InboxSyncJob,
        *,
        listed_count: int | None = None,
        fetched_count: int | None = None,
        new_count: int | None = None,
        updated_count: int | None = None,
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

    async def complete(self, job: InboxSyncJob) -> None:
        async with job.lock:
            job.status = "completed"
            job.finished_at = datetime.now(UTC)

    async def fail(self, job: InboxSyncJob, error: str) -> None:
        async with job.lock:
            job.status = "failed"
            job.error = error
            job.finished_at = datetime.now(UTC)


inbox_sync_job_store = InboxSyncJobStore()
