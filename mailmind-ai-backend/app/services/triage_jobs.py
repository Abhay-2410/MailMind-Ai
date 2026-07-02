"""In-memory triage analyze jobs and per-user session storage."""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID

from app.agents.inbox_triage_agent import TriageDecision
from app.schemas.cleanup import TriageAnalyzeResponse
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

    async def complete(self, job: TriageJob, result: TriageAnalyzeResponse) -> None:
        async with job.lock:
            job.status = "completed"
            job.progress = 1.0
            job.phase = "completed"
            job.result = result

    async def fail(self, job: TriageJob, error: str) -> None:
        async with job.lock:
            job.status = "failed"
            job.error = error


triage_job_store = TriageJobStore()
