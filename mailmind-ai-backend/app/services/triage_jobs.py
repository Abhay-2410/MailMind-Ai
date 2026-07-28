"""In-memory triage analyze jobs with Redis progress snapshots."""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID

from app.agents.inbox_triage_agent import TriageDecision
from app.schemas.cleanup import TriageAnalyzeResponse
from app.services.job_progress_redis import load_job_snapshot, save_job_snapshot
from app.utils.gmail_pagination_helpers import TriageCandidate


@dataclass
class TriageJob:
    job_id: str
    user_id: UUID
    status: str = "pending"
    progress: float = 0.0
    processed: int = 0
    total: int = 0
    phase: str = "pending"
    result: TriageAnalyzeResponse | None = None
    error: str | None = None
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    def snapshot(self) -> dict:
        return {
            "job_id": self.job_id,
            "user_id": str(self.user_id),
            "status": self.status,
            "progress": self.progress,
            "processed": self.processed,
            "total": self.total,
            "phase": self.phase,
            "error": self.error,
            "result": self.result.model_dump(mode="json") if self.result else None,
        }


@dataclass
class TriageSession:
    user_id: UUID
    decisions: dict[str, TriageDecision]
    candidates: dict[str, TriageCandidate]
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class TriageJobStore:
    def __init__(self) -> None:
        self._jobs: dict[str, TriageJob] = {}
        self._sessions: dict[UUID, TriageSession] = {}

    def create(self, user_id: UUID) -> TriageJob:
        job = TriageJob(job_id=str(uuid.uuid4()), user_id=user_id)
        self._jobs[job.job_id] = job
        return job

    def get(self, job_id: str) -> TriageJob | None:
        return self._jobs.get(job_id)

    async def get_async(self, job_id: str) -> TriageJob | None:
        job = self._jobs.get(job_id)
        if job:
            return job
        snap = await load_job_snapshot("triage", job_id)
        if not snap:
            return None
        try:
            restored = TriageJob(
                job_id=snap["job_id"],
                user_id=UUID(snap["user_id"]),
                status=snap.get("status", "pending"),
                progress=float(snap.get("progress") or 0),
                processed=int(snap.get("processed") or 0),
                total=int(snap.get("total") or 0),
                phase=snap.get("phase", "pending"),
                error=snap.get("error"),
            )
            if snap.get("result"):
                restored.result = TriageAnalyzeResponse.model_validate(snap["result"])
            self._jobs[job_id] = restored
            return restored
        except Exception:
            return None

    def get_session(self, user_id: UUID) -> TriageSession | None:
        return self._sessions.get(user_id)

    def save_session(
        self,
        user_id: UUID,
        decisions: list[TriageDecision],
        candidates: list[TriageCandidate],
    ) -> TriageSession:
        session = TriageSession(
            user_id=user_id,
            decisions={d.message_id: d for d in decisions},
            candidates={c.message.gmail_id: c for c in candidates},
        )
        self._sessions[user_id] = session
        return session

    async def update_progress(
        self,
        job: TriageJob,
        *,
        processed: int,
        total: int,
        phase: str,
    ) -> None:
        async with job.lock:
            job.processed = processed
            job.total = total
            job.phase = phase
            job.progress = processed / total if total else 0.0
            job.status = "running"
            payload = job.snapshot()
        await save_job_snapshot("triage", job.job_id, payload)

    async def complete(self, job: TriageJob, result: TriageAnalyzeResponse) -> None:
        async with job.lock:
            job.status = "completed"
            job.progress = 1.0
            job.phase = "completed"
            job.result = result
            payload = job.snapshot()
        await save_job_snapshot("triage", job.job_id, payload)

    async def fail(self, job: TriageJob, error: str) -> None:
        async with job.lock:
            job.status = "failed"
            job.error = error
            payload = job.snapshot()
        await save_job_snapshot("triage", job.job_id, payload)


triage_job_store = TriageJobStore()
