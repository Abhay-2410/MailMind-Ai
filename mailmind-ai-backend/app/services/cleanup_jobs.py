"""In-memory analyze job progress tracking with Redis snapshots."""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from uuid import UUID

from app.schemas.cleanup import CleanupAnalyzeResponse, SmartCleanupCategory
from app.services.job_progress_redis import load_job_snapshot, save_job_snapshot


@dataclass
class CleanupJob:
    job_id: str
    user_id: UUID
    category: SmartCleanupCategory
    status: str = "pending"
    progress: float = 0.0
    processed: int = 0
    total: int = 0
    result: CleanupAnalyzeResponse | None = None
    error: str | None = None
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    def snapshot(self) -> dict:
        return {
            "job_id": self.job_id,
            "user_id": str(self.user_id),
            "category": self.category.value if hasattr(self.category, "value") else str(self.category),
            "status": self.status,
            "progress": self.progress,
            "processed": self.processed,
            "total": self.total,
            "error": self.error,
            "result": self.result.model_dump(mode="json") if self.result else None,
        }


class CleanupJobStore:
    def __init__(self) -> None:
        self._jobs: dict[str, CleanupJob] = {}

    def create(self, user_id: UUID, category: SmartCleanupCategory) -> CleanupJob:
        job = CleanupJob(job_id=str(uuid.uuid4()), user_id=user_id, category=category)
        self._jobs[job.job_id] = job
        return job

    def get(self, job_id: str) -> CleanupJob | None:
        return self._jobs.get(job_id)

    async def get_async(self, job_id: str) -> CleanupJob | None:
        job = self._jobs.get(job_id)
        if job:
            return job
        snap = await load_job_snapshot("cleanup", job_id)
        if not snap:
            return None
        try:
            category = SmartCleanupCategory(snap["category"])
            restored = CleanupJob(
                job_id=snap["job_id"],
                user_id=UUID(snap["user_id"]),
                category=category,
                status=snap.get("status", "pending"),
                progress=float(snap.get("progress") or 0),
                processed=int(snap.get("processed") or 0),
                total=int(snap.get("total") or 0),
                error=snap.get("error"),
            )
            if snap.get("result"):
                restored.result = CleanupAnalyzeResponse.model_validate(snap["result"])
            self._jobs[job_id] = restored
            return restored
        except Exception:
            return None

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
            payload = job.snapshot()
        await save_job_snapshot("cleanup", job.job_id, payload)

    async def complete(self, job: CleanupJob, result: CleanupAnalyzeResponse) -> None:
        async with job.lock:
            job.status = "completed"
            job.progress = 1.0
            job.result = result
            payload = job.snapshot()
        await save_job_snapshot("cleanup", job.job_id, payload)

    async def fail(self, job: CleanupJob, error: str) -> None:
        async with job.lock:
            job.status = "failed"
            job.error = error
            payload = job.snapshot()
        await save_job_snapshot("cleanup", job.job_id, payload)


cleanup_job_store = CleanupJobStore()
