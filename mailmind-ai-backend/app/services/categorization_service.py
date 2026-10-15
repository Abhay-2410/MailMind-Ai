"""Applies layered categorization and priority scores to stored emails.

Order of authority: user correction > sender rule > deterministic rules / sender
history / thread consistency / Gmail tabs > AI (only for low-confidence emails).
"""

import asyncio
import json
import logging
from collections import Counter, defaultdict
from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import load_only

from app.ai.prompts.categorize import BATCH_CATEGORIZE_SYSTEM, build_batch_categorize_prompt
from app.core.config import get_settings
from app.core.exceptions import AppError
from app.models.ai_usage import AIActionType
from app.models.category import Category, CategorySource, EmailCategory, SenderRule
from app.models.email import Email
from app.models.user import User
from app.services.ai_service import AIService
from app.services.classifier import (
    AI_CONFIDENCE_THRESHOLD,
    CONTENT_CATEGORIES,
    SENDER_HISTORY_MIN_EMAILS,
    Classification,
    ClassifierContext,
    EmailSignals,
    classify,
    compute_priority,
    signals_from_fields,
)

logger = logging.getLogger(__name__)

# Sources a later deterministic pass may freely replace.
REPLACEABLE_SOURCES = frozenset(
    {
        CategorySource.RULE.value,
        CategorySource.SENDER_HISTORY.value,
        CategorySource.THREAD.value,
        CategorySource.GMAIL.value,
    }
)
# Sources trusted enough to teach sender history and anchor threads.
TRUSTED_SOURCES = frozenset(
    {
        CategorySource.USER.value,
        CategorySource.SENDER_RULE.value,
        CategorySource.RULE.value,
        CategorySource.AI.value,
    }
)
# History rows count as evidence too; otherwise relabelling an email "by sender
# history" removes its own evidence and the label flip-flops between passes.
HISTORY_EVIDENCE_SOURCES = TRUSTED_SOURCES | {CategorySource.SENDER_HISTORY.value}
TRUSTED_MIN_CONFIDENCE = 0.8
THREAD_ANCHOR_MIN_CONFIDENCE = 0.85
THREAD_CONFIDENCE = 0.8
AI_OVERRIDE_MIN_CONFIDENCE = 0.9
AI_ESCALATION_CONFIDENCE = 0.6
AI_BATCH_SIZE = 15
AI_RATE_LIMIT_WAITS = (10, 20, 40)
FEW_SHOT_EXAMPLES = 8
ID_CHUNK = 500

SIGNAL_COLUMNS = (
    Email.id,
    Email.user_id,
    Email.thread_id,
    Email.sender,
    Email.sender_name,
    Email.subject,
    Email.preview,
    Email.labels,
    Email.is_bulk,
    Email.is_automated,
    Email.is_starred,
    Email.is_important,
    Email.priority_score,
    Email.received_at,
)


def signals_for_email(email: Email) -> EmailSignals:
    return signals_from_fields(
        sender=email.sender,
        subject=email.subject,
        preview=email.preview,
        sender_name=email.sender_name,
        labels=email.labels,
        is_bulk=bool(email.is_bulk),
        is_automated=bool(email.is_automated),
        is_starred=bool(email.is_starred),
        is_important=bool(email.is_important),
    )


def is_legacy(row: Category) -> bool:
    """'important' used to be a category; it is now the separate priority flag."""
    return row.category == EmailCategory.IMPORTANT and row.source != CategorySource.USER.value


def should_replace(existing: Category | None, new: Classification) -> bool:
    if existing is None:
        return True
    if existing.source == CategorySource.USER.value:
        return False
    if is_legacy(existing):
        return True
    if new.source in (CategorySource.USER, CategorySource.SENDER_RULE):
        return True
    if existing.source == CategorySource.SENDER_RULE.value:
        return False
    if existing.source in REPLACEABLE_SOURCES:
        return True
    # Existing AI result: only a clearly stronger signal wins.
    return new.confidence >= max(AI_OVERRIDE_MIN_CONFIDENCE, existing.confidence)


class CategorizationService:
    def __init__(self, ai_service: AIService | None = None) -> None:
        self.ai_service = ai_service or AIService()
        self.settings = get_settings()

    # ------------------------------------------------------------------ context

    async def load_context(self, db: AsyncSession, user: User) -> ClassifierContext:
        contacted: set[str] = set()
        sent_rows = await db.execute(
            select(Email.recipients).where(
                Email.user_id == user.id,
                Email.recipients.is_not(None),
                Email.labels.like('%"SENT"%'),
            )
        )
        for (recipients,) in sent_rows.all():
            contacted.update(addr.strip() for addr in (recipients or "").split(",") if addr.strip())
        contacted.discard((user.email or "").lower())

        rules_rows = await db.execute(
            select(SenderRule.sender, SenderRule.category).where(SenderRule.user_id == user.id)
        )
        sender_rules = {sender: category for sender, category in rules_rows.all()}

        history_rows = await db.execute(
            select(Email.sender, Category.category, func.count(Category.id))
            .join(Category, Category.email_id == Email.id)
            .where(
                Email.user_id == user.id,
                Category.source.in_(HISTORY_EVIDENCE_SOURCES),
                Category.confidence >= TRUSTED_MIN_CONFIDENCE,
                Category.category != EmailCategory.IMPORTANT,
            )
            .group_by(Email.sender, Category.category)
        )
        per_sender: dict[str, Counter[EmailCategory]] = defaultdict(Counter)
        for sender, category, count in history_rows.all():
            per_sender[sender][category] += int(count)

        sender_history: dict[str, tuple[EmailCategory, float, int]] = {}
        for sender, counts in per_sender.items():
            total = sum(counts.values())
            if total < SENDER_HISTORY_MIN_EMAILS:
                continue
            category, top = counts.most_common(1)[0]
            sender_history[sender] = (category, top / total, total)

        return ClassifierContext(
            user_email=(user.email or "").lower(),
            contacted=contacted,
            sender_rules=sender_rules,
            sender_history=sender_history,
        )

    async def _load_categories(self, db: AsyncSession, email_ids: Sequence[UUID]) -> dict[UUID, Category]:
        rows: dict[UUID, Category] = {}
        for start in range(0, len(email_ids), ID_CHUNK):
            chunk = list(email_ids[start : start + ID_CHUNK])
            result = await db.execute(select(Category).where(Category.email_id.in_(chunk)))
            for row in result.scalars().all():
                rows[row.email_id] = row
        return rows

    @staticmethod
    def _write(
        db: AsyncSession,
        categories: dict[UUID, Category],
        email_id: UUID,
        classification: Classification,
        model_used: str | None = None,
    ) -> Category:
        row = categories.get(email_id)
        if row is None:
            row = Category(email_id=email_id)
            db.add(row)
            categories[email_id] = row
        row.category = classification.category
        row.confidence = round(classification.confidence, 3)
        row.source = classification.source.value
        row.reason = classification.reason[:255]
        row.model_used = model_used or classification.source.value
        return row

    # ------------------------------------------------------------ deterministic

    async def classify_emails(
        self,
        db: AsyncSession,
        user: User,
        emails: Sequence[Email],
        *,
        ctx: ClassifierContext | None = None,
    ) -> int:
        """Deterministic categories + priority for the given emails. Returns rows changed."""
        if not emails:
            return 0
        ctx = ctx or await self.load_context(db, user)
        categories = await self._load_categories(db, [email.id for email in emails])
        changed = 0

        for email in emails:
            signals = signals_for_email(email)
            existing = categories.get(email.id)
            result = classify(signals, ctx)
            if result is not None and should_replace(existing, result):
                if (
                    existing is None
                    or existing.category != result.category
                    or existing.source != result.source.value
                    or abs(existing.confidence - result.confidence) > 0.001
                ):
                    self._write(db, categories, email.id, result)
                    changed += 1
            elif result is None and existing is not None and is_legacy(existing):
                await db.delete(existing)
                del categories[email.id]
                changed += 1
            final = categories.get(email.id)
            email.priority_score = compute_priority(signals, final.category if final else None, ctx)

        await db.flush()
        return changed

    async def _thread_pass(
        self,
        db: AsyncSession,
        emails: Sequence[Email],
        categories: dict[UUID, Category],
    ) -> int:
        by_thread: dict[str, list[Email]] = defaultdict(list)
        for email in emails:
            if email.thread_id:
                by_thread[email.thread_id].append(email)

        changed = 0
        for siblings in by_thread.values():
            if len(siblings) < 2:
                continue
            anchors = [
                categories[email.id]
                for email in siblings
                if email.id in categories
                and categories[email.id].source in TRUSTED_SOURCES
                and categories[email.id].confidence >= THREAD_ANCHOR_MIN_CONFIDENCE
                and categories[email.id].category != EmailCategory.IMPORTANT
            ]
            if not anchors:
                continue
            anchor = max(anchors, key=lambda row: row.confidence)
            adopt = Classification(
                anchor.category,
                THREAD_CONFIDENCE,
                CategorySource.THREAD,
                f"Same conversation as an email filed as {anchor.category.value}",
            )
            for email in siblings:
                current = categories.get(email.id)
                if current is not None and not is_legacy(current):
                    if current.confidence >= AI_CONFIDENCE_THRESHOLD:
                        continue
                    if current.source not in REPLACEABLE_SOURCES:
                        continue
                self._write(db, categories, email.id, adopt)
                changed += 1
        await db.flush()
        return changed

    # ----------------------------------------------------------------------- AI

    async def _few_shot_examples(self, db: AsyncSession, user_id: UUID) -> list[dict]:
        result = await db.execute(
            select(Email.sender, Email.subject, Category.category)
            .join(Category, Category.email_id == Email.id)
            .where(Email.user_id == user_id, Category.source == CategorySource.USER.value)
            .order_by(Category.updated_at.desc())
            .limit(FEW_SHOT_EXAMPLES)
        )
        return [
            {"sender": sender, "subject": subject or "", "category": category.value}
            for sender, subject, category in result.all()
        ]

    async def _complete_with_backoff(self, provider, **kwargs):
        for wait in (*AI_RATE_LIMIT_WAITS, None):
            try:
                return await provider.complete_json(**kwargs)
            except AppError as exc:
                if exc.status_code != 429 or wait is None:
                    raise
                logger.info("AI rate limited during categorization; waiting %ss", wait)
                await asyncio.sleep(wait)
        return None

    async def _ai_batch(
        self,
        db: AsyncSession,
        user: User,
        provider_name: str,
        model_id: str,
        payload: list[dict],
        examples: list[dict],
    ) -> dict[int, tuple[EmailCategory, float]]:
        provider = self.ai_service._get_provider(provider_name)
        result = await self._complete_with_backoff(
            provider,
            model=model_id,
            system_prompt=BATCH_CATEGORIZE_SYSTEM,
            user_prompt=build_batch_categorize_prompt(emails=payload, examples=examples),
            max_tokens=1500,
        )
        if result is None:
            return {}
        await self.ai_service._track_usage(
            db,
            user.id,
            AIActionType.CATEGORIZE,
            provider=result.provider,
            model=result.model,
            prompt_tokens=result.prompt_tokens,
            completion_tokens=result.completion_tokens,
            total_tokens=result.total_tokens,
            metadata={"batch_size": len(payload)},
        )
        try:
            parsed = json.loads(result.content)
        except json.JSONDecodeError:
            logger.warning("AI categorization returned invalid JSON; batch skipped")
            return {}

        out: dict[int, tuple[EmailCategory, float]] = {}
        entries = parsed.get("results", []) if isinstance(parsed, dict) else []
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            try:
                index = int(entry.get("index"))
                category = EmailCategory(str(entry.get("category", "")).strip().lower())
            except (TypeError, ValueError):
                continue
            if category not in CONTENT_CATEGORIES:
                continue
            out[index] = (category, AIService._coerce_confidence(entry.get("confidence")))
        return out

    async def _ai_pass(
        self,
        db: AsyncSession,
        user: User,
        emails: Sequence[Email],
        categories: dict[UUID, Category],
        ctx: ClassifierContext,
        *,
        limit: int,
    ) -> int:
        candidates = [
            email
            for email in emails
            if (row := categories.get(email.id)) is None
            or is_legacy(row)
            or (row.source in REPLACEABLE_SOURCES and row.confidence < AI_CONFIDENCE_THRESHOLD)
        ]
        candidates.sort(key=lambda email: email.received_at, reverse=True)
        candidates = candidates[:limit]
        if not candidates:
            return 0

        provider_name, model_id = await self.ai_service._resolve_model(db, user.id)
        escalation_model = self.settings.AI_ESCALATION_MODEL
        can_escalate = provider_name == "groq" and bool(escalation_model) and escalation_model != model_id
        examples = await self._few_shot_examples(db, user.id)
        categorized = 0

        for start in range(0, len(candidates), AI_BATCH_SIZE):
            chunk = candidates[start : start + AI_BATCH_SIZE]
            payload = []
            for index, email in enumerate(chunk):
                signals = signals_for_email(email)
                current = categories.get(email.id)
                labels = set(signals.labels)
                tab = next(
                    (
                        name
                        for label, name in (
                            ("CATEGORY_PROMOTIONS", "promotions"),
                            ("CATEGORY_SOCIAL", "social"),
                            ("CATEGORY_FORUMS", "forums"),
                            ("CATEGORY_UPDATES", "updates"),
                            ("CATEGORY_PERSONAL", "primary"),
                        )
                        if label in labels
                    ),
                    None,
                )
                payload.append(
                    {
                        "index": index,
                        "sender": email.sender,
                        "sender_name": email.sender_name,
                        "subject": email.subject,
                        "preview": email.preview or "",
                        "gmail_tab": tab,
                        "bulk": signals.is_bulk,
                        "automated": signals.is_automated,
                        "you_emailed_sender": signals.sender in ctx.contacted,
                        "current_guess": current.category.value if current else None,
                    }
                )

            try:
                results = await self._ai_batch(db, user, provider_name, model_id, payload, examples)
            except AppError as exc:
                logger.warning("AI categorization stopped: %s", exc.message)
                break

            low = [index for index, (_, confidence) in results.items() if confidence < AI_ESCALATION_CONFIDENCE]
            used_model = {index: model_id for index in results}
            if can_escalate and low:
                try:
                    retry_payload = [{**payload[index], "index": pos} for pos, index in enumerate(low)]
                    escalated = await self._ai_batch(
                        db, user, provider_name, escalation_model, retry_payload, examples
                    )
                    for pos, (category, confidence) in escalated.items():
                        if 0 <= pos < len(low):
                            results[low[pos]] = (category, confidence)
                            used_model[low[pos]] = escalation_model
                except AppError as exc:
                    logger.info("AI escalation skipped: %s", exc.message)

            for index, (category, confidence) in results.items():
                if not 0 <= index < len(chunk):
                    continue
                email = chunk[index]
                ai_result = Classification(
                    category, confidence, CategorySource.AI, f"AI ({used_model[index]})"
                )
                current = categories.get(email.id)
                if current is not None and current.source not in REPLACEABLE_SOURCES and not is_legacy(current):
                    continue
                self._write(db, categories, email.id, ai_result, model_used=used_model[index])
                email.priority_score = compute_priority(signals_for_email(email), category, ctx)
                categorized += 1
            await db.commit()

        return categorized

    # ---------------------------------------------------------------- pipelines

    async def _load_emails(
        self,
        db: AsyncSession,
        user_id: UUID,
        email_ids: Sequence[UUID] | None = None,
    ) -> list[Email]:
        query = select(Email).options(load_only(*SIGNAL_COLUMNS)).where(Email.user_id == user_id)
        if email_ids is None:
            result = await db.execute(query)
            return list(result.scalars().all())
        emails: list[Email] = []
        for start in range(0, len(email_ids), ID_CHUNK):
            chunk = list(email_ids[start : start + ID_CHUNK])
            result = await db.execute(query.where(Email.id.in_(chunk)))
            emails.extend(result.scalars().all())
        return emails

    async def recategorize_user(
        self,
        db: AsyncSession,
        user: User,
        *,
        ai_limit: int = 150,
        use_ai: bool = True,
    ) -> dict[str, int]:
        """Full pass over a user's mailbox: rules, thread consistency, then AI for the rest."""
        ctx = await self.load_context(db, user)
        emails = await self._load_emails(db, user.id)
        deterministic = await self.classify_emails(db, user, emails, ctx=ctx)
        categories = await self._load_categories(db, [email.id for email in emails])
        threaded = await self._thread_pass(db, emails, categories)
        for email in emails:
            row = categories.get(email.id)
            email.priority_score = compute_priority(signals_for_email(email), row.category if row else None, ctx)
        await db.commit()

        ai_count = 0
        if use_ai and ai_limit > 0 and self._ai_configured():
            ai_count = await self._ai_pass(db, user, emails, categories, ctx, limit=ai_limit)
        return {
            "emails": len(emails),
            "deterministic": deterministic,
            "thread": threaded,
            "ai": ai_count,
        }

    async def categorize_new_emails(
        self,
        db: AsyncSession,
        user: User,
        email_ids: Sequence[UUID],
        *,
        ai_limit: int = 30,
    ) -> int:
        """Incremental path used after a sync: classify fresh emails, AI only where unsure."""
        if not email_ids:
            return 0
        ctx = await self.load_context(db, user)
        emails = await self._load_emails(db, user.id, email_ids)
        changed = await self.classify_emails(db, user, emails, ctx=ctx)
        await db.commit()
        if ai_limit > 0 and self._ai_configured():
            categories = await self._load_categories(db, [email.id for email in emails])
            changed += await self._ai_pass(db, user, emails, categories, ctx, limit=ai_limit)
        return changed

    def _ai_configured(self) -> bool:
        return bool(self.settings.GROQ_API_KEY or self.settings.OPENROUTER_API_KEY)

    # -------------------------------------------------------------- corrections

    async def set_user_category(
        self,
        db: AsyncSession,
        user: User,
        email_id: UUID,
        category: EmailCategory,
        *,
        apply_to_sender: bool = True,
    ) -> tuple[Email, int]:
        """Record a user correction; optionally pin the sender. Returns (email, other emails updated)."""
        result = await db.execute(select(Email).where(Email.id == email_id, Email.user_id == user.id))
        email = result.scalar_one_or_none()
        if email is None:
            raise AppError("Email not found", status_code=404)

        categories = await self._load_categories(db, [email.id])
        self._write(
            db,
            categories,
            email.id,
            Classification(category, 1.0, CategorySource.USER, "Set by you"),
            model_used=CategorySource.USER.value,
        )

        updated = 0
        if apply_to_sender:
            rule_result = await db.execute(
                select(SenderRule).where(SenderRule.user_id == user.id, SenderRule.sender == email.sender)
            )
            rule = rule_result.scalar_one_or_none()
            if rule is None:
                db.add(SenderRule(user_id=user.id, sender=email.sender, category=category))
            else:
                rule.category = category
            await db.flush()

            ctx = await self.load_context(db, user)
            siblings = await db.execute(
                select(Email)
                .options(load_only(*SIGNAL_COLUMNS))
                .where(Email.user_id == user.id, Email.sender == email.sender, Email.id != email.id)
            )
            updated = await self.classify_emails(db, user, list(siblings.scalars().all()), ctx=ctx)
        else:
            ctx = await self.load_context(db, user)

        email.priority_score = compute_priority(signals_for_email(email), category, ctx)
        await db.commit()
        await db.refresh(email)
        return email, updated
