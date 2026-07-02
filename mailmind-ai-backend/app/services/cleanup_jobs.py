"""In-memory analyze job progress tracking."""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from typing import Any

from app.schemas.cleanup import CleanupAnalyzeResponse, SmartCleanupCategory


@dataclass
class CleanupJob:
    job_id: str
    category: SmartCleanupCategory
    status: str = "pending"
    progress: float = 0.0
    processed: int = 0
    total: int = 0
    result: CleanupAnalyzeResponse | None = None
    error: str | None = None
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)


class CleanupJobStore:
    def __init__(self) -> None:
        self._jobs: dict[str, CleanupJob] = {}

    def create(self, category: SmartCleanupCategory) -> CleanupJob:
        job = CleanupJob(job_id=str(uuid.uuid4()), category=category)
        self._jobs[job.job_id] = job
        return job

    def get(self, job_id: str) -> CleanupJob | None:
        return self._jobs.get(job_id)

    async def update_progress(
        self,
        job: CleanupJob,
        *,
        processed: int,
        total: int,
    ) -> None:
        async with job.lock:
            job.processed = processed
            job.total = total
            job.progress = processed / total if total else 0.0
            job.status = "running"

    async def complete(self, job: CleanupJob, result: CleanupAnalyzeResponse) -> None:
        async with job.lock:
            job.status = "completed"
            job.progress = 1.0
            job.result = result

    async def fail(self, job: CleanupJob, error: str) -> None:
        async with job.lock:
            job.status = "failed"
            job.error = error


cleanup_job_store = CleanupJobStore()
