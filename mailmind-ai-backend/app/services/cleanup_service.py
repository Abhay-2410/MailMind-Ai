from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from uuid import UUID

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal

from app.agents.primary_inbox_agent import PrimaryInboxAgent
from app.agents.inbox_triage_agent import ImportanceTier as AgentImportanceTier
from app.agents.inbox_triage_agent import InboxTriageAgent, TriageDecision
from app.core.exceptions import AppError
from app.models.account import Account
from app.models.email import Email
from app.models.user import User
from app.schemas.cleanup import (
    SMART_CLEANUP_CONFIDENCE,
    SMART_CLEANUP_LABELS,
    CleanupAnalyzeMessage,
    CleanupAnalyzeProgressResponse,
    CleanupAnalyzeRequest,
    CleanupAnalyzeResponse,
    CleanupCountItem,
    CleanupCountsResponse,
    CleanupDeleteRequest,
    CleanupDeleteResponse,
    CleanupRestoreRequest,
    CleanupRestoreResponse,
    ImportanceTier,
    SmartCleanupCategory,
    TriageAnalyzeProgressResponse,
    TriageAnalyzeRequest,
    TriageAnalyzeResponse,
    TriageClassificationItem,
    TriageDeleteRequest,
    TriageDeleteResponse,
    TriageDeleteTier,
    TriageSampleEmails,
)
from app.services.triage_jobs import triage_job_store
from app.utils.gmail_pagination_helpers import GmailPaginationHelpers
from app.services.cleanup_jobs import cleanup_job_store
from app.services.email_service import EmailService
from app.services.gmail_service import GmailService
from app.utils.gmail_cleanup_helpers import GmailCleanupHelpers

logger = logging.getLogger(__name__)

HEURISTIC_CONFIDENCE = 0.5


class CleanupService:
    def __init__(
        self,
        email_service: EmailService | None = None,
        gmail_service: GmailService | None = None,
        helpers: GmailCleanupHelpers | None = None,
        agent: PrimaryInboxAgent | None = None,
        triage_agent: InboxTriageAgent | None = None,
        pagination: GmailPaginationHelpers | None = None,
    ) -> None:
        self.email_service = email_service or EmailService()
        self.gmail = gmail_service or GmailService()
        self.helpers = helpers or GmailCleanupHelpers(self.gmail)
        self.agent = agent or PrimaryInboxAgent()
        self.triage_agent = triage_agent or InboxTriageAgent()
        self.pagination = pagination or GmailPaginationHelpers(self.gmail, self.helpers)

    async def get_counts(self, db: AsyncSession, user: User) -> CleanupCountsResponse:
        account = await self.email_service.get_primary_account(db, user.id)

        items: list[CleanupCountItem] = []
        for category in SmartCleanupCategory:
            count = await self.helpers.count_category_messages(account, db, category)
            items.append(
                CleanupCountItem(
                    category=category,
                    label=SMART_CLEANUP_LABELS[category],
                    count=count,
                    confidence=SMART_CLEANUP_CONFIDENCE[category],
                )
            )
        return CleanupCountsResponse(categories=items)

    async def analyze(
        self,
        db: AsyncSession,
        user: User,
        payload: CleanupAnalyzeRequest,
        *,
        job_id: str | None = None,
    ) -> CleanupAnalyzeResponse:
        account = await self.email_service.get_primary_account(db, user.id)
        job = cleanup_job_store.get(job_id) if job_id else None
        access_token = await self.gmail.ensure_valid_access_token(account, db)

        async def progress(processed: int, total: int) -> None:
            if job:
                await cleanup_job_store.update_progress(job, processed=processed, total=total)

        message_ids = await self.helpers.collect_category_message_ids(
            account, db, payload.category
        )
        total_scanned = len(message_ids)

        if payload.category == SmartCleanupCategory.PRIMARY:
            result = await self._analyze_primary(
                account,
                db,
                access_token,
                user_email=account.email,
                message_ids=message_ids,
                dry_run=payload.dry_run,
                progress=progress,
            )
        else:
            result = await self._analyze_heuristic(
                access_token,
                user_email=account.email,
                category=payload.category,
                message_ids=message_ids,
                dry_run=payload.dry_run,
                progress=progress,
            )

        response = CleanupAnalyzeResponse(
            category=payload.category,
            label=SMART_CLEANUP_LABELS[payload.category],
            total_scanned=total_scanned,
            kept_count=result["kept_count"],
            delete_count=len(result["message_ids"]),
            message_ids=result["message_ids"],
            samples=result["samples"],
            messages=result["messages"],
            dry_run=payload.dry_run,
            job_id=job_id,
            status="completed",
            progress=1.0,
        )

        if job:
            await cleanup_job_store.complete(job, response)
        return response

    async def start_analyze_job(
        self,
        db: AsyncSession,
        user: User,
        payload: CleanupAnalyzeRequest,
    ) -> CleanupAnalyzeProgressResponse:
        user_id = user.id
        job = cleanup_job_store.create(user.id, payload.category)

        async def run() -> None:
            try:
                async with AsyncSessionLocal() as session:
                    from sqlalchemy import select

                    result = await session.execute(select(User).where(User.id == user_id))
                    db_user = result.scalar_one()
                    await self.analyze(session, db_user, payload, job_id=job.job_id)
            except Exception as exc:  # noqa: BLE001 — background job must capture failures
                logger.exception("Cleanup analyze job failed")
                await cleanup_job_store.fail(job, str(exc))

        asyncio.create_task(run())
        return CleanupAnalyzeProgressResponse(
            job_id=job.job_id,
            category=payload.category,
            status="pending",
            progress=0.0,
            processed=0,
            total=0,
        )

    async def get_analyze_progress(
        self,
        job_id: str,
        user: User,
    ) -> CleanupAnalyzeProgressResponse:
        job = await cleanup_job_store.get_async(job_id)
        if not job or job.user_id != user.id:
            raise AppError("Analyze job not found", status_code=404)

        async with job.lock:
            return CleanupAnalyzeProgressResponse(
                job_id=job.job_id,
                category=job.category,
                status=job.status,
                progress=job.progress,
                processed=job.processed,
                total=job.total,
                result=job.result,
                error=job.error,
            )

    async def _analyze_heuristic(
        self,
        access_token: str,
        *,
        user_email: str,
        category: SmartCleanupCategory,
        message_ids: list[str],
        dry_run: bool,
        progress: Callable[[int, int], Awaitable[None]] | None = None,
    ) -> dict:
        deletable, kept_ids = await self.helpers.filter_heuristic_candidates(
            access_token,
            message_ids,
            user_email,
            progress_callback=progress,
        )
        delete_ids = [c.message.gmail_id for c in deletable]
        samples = [c.message.subject for c in deletable[:3]]
        messages = [
            CleanupAnalyzeMessage(
                message_id=c.message.gmail_id,
                confidence=HEURISTIC_CONFIDENCE,
                subject=c.message.subject,
                reason="Label + heuristic match",
            )
            for c in deletable
        ]
        return {
            "message_ids": delete_ids,
            "kept_count": len(kept_ids),
            "samples": samples,
            "messages": messages,
        }

    async def _analyze_primary(
        self,
        account: Account,
        db: AsyncSession,
        access_token: str,
        *,
        user_email: str,
        message_ids: list[str],
        dry_run: bool,
        progress: Callable[[int, int], Awaitable[None]] | None = None,
    ) -> dict:
        contacts = await self.helpers.fetch_contact_emails(access_token, user_email)
        contacts_available = bool(contacts)

        candidates = await self.helpers.build_primary_candidates(
            access_token,
            message_ids,
            user_email,
            progress_callback=progress,
        )

        decisions = await self.agent.analyze_candidates(
            candidates,
            dry_run=dry_run,
            contacts=contacts,
            contacts_available=contacts_available,
            progress_callback=progress,
        )

        delete_ids = self.agent.deletable_ids(decisions)
        candidate_subjects = {c.message.gmail_id: c.message.subject for c in candidates}
        samples = [candidate_subjects[mid] for mid in delete_ids[:3] if mid in candidate_subjects]
        messages = [
            CleanupAnalyzeMessage(
                message_id=d.message_id,
                confidence=d.confidence,
                subject=next(
                    (c.message.subject for c in candidates if c.message.gmail_id == d.message_id),
                    None,
                ),
                reason=d.reason,
            )
            for d in decisions
            if d.message_id in delete_ids
        ]
        kept_count = len(message_ids) - len(delete_ids)
        return {
            "message_ids": delete_ids,
            "kept_count": kept_count,
            "samples": samples,
            "messages": messages,
        }

    async def delete_messages(
        self,
        db: AsyncSession,
        user: User,
        payload: CleanupDeleteRequest,
    ) -> CleanupDeleteResponse:
        account = await self.email_service.get_primary_account(db, user.id)
        access_token = await self.gmail.ensure_access_token_for_delete(account, db)

        if payload.permanent:
            if not self.gmail.scope_includes_gmail_delete(account.oauth_scopes):
                raise AppError(
                    "Full Gmail access is required for permanent delete. "
                    "Sign out, sign in with Google again, and allow all Gmail permissions.",
                    status_code=403,
                )
            deleted, failed = await self.helpers.permanent_delete_messages(
                access_token, payload.message_ids
            )
        else:
            deleted, failed = await self.helpers.trash_messages(
                access_token, payload.message_ids
            )

        if deleted:
            await self._purge_local(db, user.id, [mid for mid in payload.message_ids if mid not in failed])

        return CleanupDeleteResponse(
            deleted=deleted,
            failed=failed,
            trashed=not payload.permanent,
        )

    async def restore_messages(
        self,
        db: AsyncSession,
        user: User,
        payload: CleanupRestoreRequest,
    ) -> CleanupRestoreResponse:
        account = await self.email_service.get_primary_account(db, user.id)
        access_token = await self.gmail.ensure_valid_access_token(account, db)
        restored, failed = await self.helpers.untrash_messages(
            access_token, payload.message_ids
        )
        return CleanupRestoreResponse(restored=restored, failed=failed)

    async def _purge_local(self, db: AsyncSession, user_id: UUID, gmail_ids: list[str]) -> None:
        await db.execute(
            delete(Email).where(
                Email.user_id == user_id,
                Email.gmail_id.in_(gmail_ids),
            )
        )
        await db.commit()

    async def analyze_triage(
        self,
        db: AsyncSession,
        user: User,
        payload: TriageAnalyzeRequest,
        *,
        job_id: str | None = None,
    ) -> TriageAnalyzeResponse:
        account = await self.email_service.get_primary_account(db, user.id)
        access_token = await self.gmail.ensure_valid_access_token(account, db)
        job = triage_job_store.get(job_id) if job_id else None

        async def on_progress(processed: int, total: int, phase: str) -> None:
            if job:
                await triage_job_store.update_progress(
                    job, processed=processed, total=total, phase=phase
                )

        message_ids = await self.pagination.collect_full_inbox_message_ids(
            access_token,
            progress_callback=on_progress,
        )
        total_scanned = len(message_ids)

        if job:
            await triage_job_store.update_progress(
                job, processed=0, total=total_scanned, phase="fetching_metadata"
            )

        candidates = await self.pagination.build_triage_candidates(
            access_token,
            message_ids,
            account.email,
            progress_callback=on_progress,
        )

        if job:
            await triage_job_store.update_progress(
                job, processed=0, total=len(candidates), phase="classifying"
            )

        decisions = await self.triage_agent.classify_all(
            candidates,
            dry_run=payload.dry_run,
            progress_callback=on_progress,
        )

        triage_job_store.save_session(user.id, decisions, candidates)
        response = self._build_triage_response(
            decisions,
            total_scanned=total_scanned,
            dry_run=payload.dry_run,
            job_id=job_id,
        )

        if job:
            await triage_job_store.complete(job, response)
        return response

    def _build_triage_response(
        self,
        decisions: list[TriageDecision],
        *,
        total_scanned: int,
        dry_run: bool,
        job_id: str | None,
    ) -> TriageAnalyzeResponse:
        counts = {
            ImportanceTier.CRITICAL: 0,
            ImportanceTier.IMPORTANT: 0,
            ImportanceTier.LOW_VALUE: 0,
            ImportanceTier.DISPOSABLE: 0,
        }
        samples: dict[ImportanceTier, list[str]] = {
            ImportanceTier.CRITICAL: [],
            ImportanceTier.IMPORTANT: [],
            ImportanceTier.LOW_VALUE: [],
            ImportanceTier.DISPOSABLE: [],
        }
        classifications: dict[str, TriageClassificationItem] = {}

        for decision in decisions:
            tier = ImportanceTier(decision.tier.value)
            counts[tier] += 1
            if decision.subject and len(samples[tier]) < 3:
                samples[tier].append(decision.subject)
            classifications[decision.message_id] = TriageClassificationItem(
                message_id=decision.message_id,
                tier=tier,
                safe_to_delete=decision.safe_to_delete,
                confidence=decision.confidence,
                reason=decision.reason,
                subject=decision.subject,
            )

        return TriageAnalyzeResponse(
            critical=counts[ImportanceTier.CRITICAL],
            important=counts[ImportanceTier.IMPORTANT],
            low_value=counts[ImportanceTier.LOW_VALUE],
            disposable=counts[ImportanceTier.DISPOSABLE],
            total_scanned=total_scanned,
            sample_emails=TriageSampleEmails(
                critical=samples[ImportanceTier.CRITICAL],
                important=samples[ImportanceTier.IMPORTANT],
                low_value=samples[ImportanceTier.LOW_VALUE],
                disposable=samples[ImportanceTier.DISPOSABLE],
            ),
            classifications=classifications,
            dry_run=dry_run,
            job_id=job_id,
            status="completed",
            progress=1.0,
        )

    async def start_triage_analyze_job(
        self,
        db: AsyncSession,
        user: User,
        payload: TriageAnalyzeRequest,
    ) -> TriageAnalyzeProgressResponse:
        user_id = user.id
        job = triage_job_store.create(user_id)

        async def run() -> None:
            try:
                async with AsyncSessionLocal() as session:
                    from sqlalchemy import select

                    result = await session.execute(select(User).where(User.id == user_id))
                    db_user = result.scalar_one()
                    await self.analyze_triage(session, db_user, payload, job_id=job.job_id)
            except Exception as exc:  # noqa: BLE001
                logger.exception("Triage analyze job failed")
                await triage_job_store.fail(job, str(exc))

        asyncio.create_task(run())
        return TriageAnalyzeProgressResponse(
            job_id=job.job_id,
            status="pending",
            progress=0.0,
            processed=0,
            total=0,
            phase="pending",
        )

    async def get_triage_analyze_progress(
        self,
        job_id: str,
        user: User,
    ) -> TriageAnalyzeProgressResponse:
        job = await triage_job_store.get_async(job_id)
        if not job or job.user_id != user.id:
            raise AppError("Triage analyze job not found", status_code=404)

        async with job.lock:
            return TriageAnalyzeProgressResponse(
                job_id=job.job_id,
                status=job.status,
                progress=job.progress,
                processed=job.processed,
                total=job.total,
                phase=job.phase,
                result=job.result,
                error=job.error,
            )

    async def delete_triage_tier(
        self,
        db: AsyncSession,
        user: User,
        payload: TriageDeleteRequest,
    ) -> TriageDeleteResponse:
        session = triage_job_store.get_session(user.id)
        if not session:
            raise AppError(
                "No triage analysis found — run Analyze Entire Inbox first",
                status_code=400,
            )

        eligible_tiers: set[AgentImportanceTier]
        if payload.tier == TriageDeleteTier.BOTH:
            eligible_tiers = {AgentImportanceTier.LOW_VALUE, AgentImportanceTier.DISPOSABLE}
        elif payload.tier == TriageDeleteTier.LOW_VALUE:
            eligible_tiers = {AgentImportanceTier.LOW_VALUE}
        else:
            eligible_tiers = {AgentImportanceTier.DISPOSABLE}

        delete_ids: list[str] = []
        for message_id, decision in session.decisions.items():
            if decision.tier not in eligible_tiers or not decision.safe_to_delete:
                continue
            candidate = session.candidates.get(message_id)
            if not candidate:
                continue
            enforced = self.triage_agent.apply_hard_safety(decision, candidate)
            if enforced.safe_to_delete and enforced.tier in eligible_tiers:
                delete_ids.append(message_id)

        if not delete_ids:
            return TriageDeleteResponse(deleted=0, failed=[], trashed=True, message_ids=[])

        account = await self.email_service.get_primary_account(db, user.id)
        access_token = await self.gmail.ensure_access_token_for_delete(account, db)
        deleted, failed = await self.helpers.trash_messages(access_token, delete_ids)
        kept = [mid for mid in delete_ids if mid not in failed]
        if kept:
            await self._purge_local(db, user.id, kept)

        return TriageDeleteResponse(
            deleted=deleted,
            failed=failed,
            trashed=True,
            message_ids=kept,
        )
