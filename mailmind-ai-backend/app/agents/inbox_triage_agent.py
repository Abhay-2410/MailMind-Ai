"""Full-inbox importance triage agent (Claude Sonnet 4.6 via OpenRouter)."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any

from app.ai.openrouter import get_provider
from app.core.config import Settings, get_settings
from app.core.exceptions import AppError
from app.utils.ai_json import parse_ai_json_array
from app.utils.gmail_cleanup_helpers import has_user_created_label
from app.utils.gmail_pagination_helpers import TriageCandidate

logger = logging.getLogger(__name__)

TRIAGE_AGENT_MODEL = "anthropic/claude-sonnet-4-6"
CONFIDENCE_THRESHOLD = 0.9
DEFAULT_BATCH_SIZE = 15

SYSTEM_PROMPT = """You are an inbox importance classifier. You will receive a batch of emails with metadata. For each email, classify its importance and decide if it's safe to delete.

Importance tiers:
- CRITICAL: legal, financial, employer, school, government, contracts, active tickets, anything from a known contact, anything requiring action
- IMPORTANT: personal conversations, active subscriptions, unresolved orders, recently opened newsletters
- LOW_VALUE: time-expired info, old promos, expired invites, already-read newsletters, social notifications
- DISPOSABLE: marketing with zero engagement, expired OTPs, duplicate/auto alerts with no remaining relevance

Rules:
- When uncertain between two tiers, always choose the HIGHER importance tier
- NEVER classify anything from a Contact, or anything with a reply thread, as DISPOSABLE
- NEVER classify CRITICAL or IMPORTANT emails as safe to delete

Respond ONLY in this JSON array format, one object per email in the batch:
[
  { "id": "messageId", "tier": "CRITICAL" | "IMPORTANT" | "LOW_VALUE" | "DISPOSABLE", "safe_to_delete": true | false, "confidence": 0.0–1.0, "reason": "one sentence" }
]

Only mark safe_to_delete: true if tier is LOW_VALUE or DISPOSABLE AND confidence >= 0.9."""

BACKEND_ROOT = Path(__file__).resolve().parents[2]
TRIAGE_LOG_PATH = BACKEND_ROOT / "inbox_triage_log.json"

TIER_ORDER = ("DISPOSABLE", "LOW_VALUE", "IMPORTANT", "CRITICAL")


class ImportanceTier(str, Enum):
    CRITICAL = "CRITICAL"
    IMPORTANT = "IMPORTANT"
    LOW_VALUE = "LOW_VALUE"
    DISPOSABLE = "DISPOSABLE"


@dataclass
class TriageDecision:
    message_id: str
    tier: ImportanceTier
    safe_to_delete: bool
    confidence: float
    reason: str
    subject: str | None = None
    kept_by_safety: bool = False


class InboxTriageAgent:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.provider = get_provider("openrouter", self.settings)

    def _append_log(self, entry: dict[str, Any]) -> None:
        entry["logged_at"] = datetime.now(UTC).isoformat()
        try:
            existing: list[Any] = []
            if TRIAGE_LOG_PATH.exists():
                raw = TRIAGE_LOG_PATH.read_text(encoding="utf-8").strip()
                if raw:
                    existing = json.loads(raw)
                    if not isinstance(existing, list):
                        existing = [existing]
            existing.append(entry)
            TRIAGE_LOG_PATH.write_text(json.dumps(existing, indent=2), encoding="utf-8")
        except (OSError, json.JSONDecodeError, TypeError) as exc:
            logger.warning("Failed to write inbox_triage_log.json: %s", exc)

    @staticmethod
    def _normalize_tier(raw: str) -> ImportanceTier:
        normalized = raw.upper().replace("-", "_").replace(" ", "_")
        mapping = {
            "CRITICAL": ImportanceTier.CRITICAL,
            "IMPORTANT": ImportanceTier.IMPORTANT,
            "LOW_VALUE": ImportanceTier.LOW_VALUE,
            "LOWVALUE": ImportanceTier.LOW_VALUE,
            "DISPOSABLE": ImportanceTier.DISPOSABLE,
        }
        return mapping.get(normalized, ImportanceTier.IMPORTANT)

    @staticmethod
    def _higher_tier(a: ImportanceTier, b: ImportanceTier) -> ImportanceTier:
        return a if TIER_ORDER.index(a.value) >= TIER_ORDER.index(b.value) else b

    def apply_hard_safety(
        self,
        decision: TriageDecision,
        candidate: TriageCandidate,
    ) -> TriageDecision:
        """Server-side safety overrides — never trust AI alone for deletion."""
        message = candidate.message
        tier = decision.tier
        safe = decision.safe_to_delete
        kept_by_safety = False
        reason = decision.reason

        if candidate.sender_in_contacts:
            tier = self._higher_tier(tier, ImportanceTier.IMPORTANT)
            safe = False
            kept_by_safety = True
            reason = "Sender in Google Contacts — protected"

        if candidate.user_replied_to_sender or candidate.thread.has_user_reply:
            tier = self._higher_tier(tier, ImportanceTier.IMPORTANT)
            safe = False
            kept_by_safety = True
            reason = "User replied in thread — protected"

        if candidate.has_attachment:
            safe = False
            kept_by_safety = True
            reason = "Has attachment — protected"

        if candidate.thread.message_count > 1:
            safe = False
            kept_by_safety = True
            reason = "Multi-message thread — protected"

        if message.is_starred or message.is_important:
            safe = False
            tier = self._higher_tier(tier, ImportanceTier.IMPORTANT)
            kept_by_safety = True
            reason = "Starred or Important label — protected"

        if has_user_created_label(message.labels):
            safe = False
            kept_by_safety = True
            reason = "User-created label — protected"

        if tier in (ImportanceTier.CRITICAL, ImportanceTier.IMPORTANT):
            safe = False

        if safe and (
            tier not in (ImportanceTier.LOW_VALUE, ImportanceTier.DISPOSABLE)
            or decision.confidence < CONFIDENCE_THRESHOLD
        ):
            safe = False

        return TriageDecision(
            message_id=decision.message_id,
            tier=tier,
            safe_to_delete=safe,
            confidence=decision.confidence,
            reason=reason,
            subject=decision.subject,
            kept_by_safety=kept_by_safety,
        )

    async def classify_batch(
        self,
        candidates: list[TriageCandidate],
        *,
        dry_run: bool,
    ) -> list[TriageDecision]:
        from app.utils.gmail_pagination_helpers import GmailPaginationHelpers

        if not candidates:
            return []

        payloads = [GmailPaginationHelpers.candidate_to_ai_payload(c) for c in candidates]
        user_prompt = json.dumps(payloads, ensure_ascii=False)

        try:
            result = await self.provider.complete_json(
                model=TRIAGE_AGENT_MODEL,
                system_prompt=SYSTEM_PROMPT,
                user_prompt=user_prompt,
                temperature=0.1,
                max_tokens=4096,
            )
            raw_items = parse_ai_json_array(result.content)
        except (AppError, ValueError) as exc:
            logger.warning("Triage batch failed: %s", exc)
            decisions = []
            for candidate in candidates:
                decision = TriageDecision(
                    message_id=candidate.message.gmail_id,
                    tier=ImportanceTier.IMPORTANT,
                    safe_to_delete=False,
                    confidence=0.0,
                    reason="Agent unavailable — kept by default",
                    subject=candidate.message.subject,
                    kept_by_safety=True,
                )
                self._append_log(
                    {**decision.__dict__, "tier": decision.tier.value, "dry_run": dry_run, "source": "agent_error"}
                )
                decisions.append(decision)
            return decisions

        by_id = {item.get("id"): item for item in raw_items if item.get("id")}
        decisions: list[TriageDecision] = []

        for candidate in candidates:
            mid = candidate.message.gmail_id
            item = by_id.get(mid, {})
            tier = self._normalize_tier(str(item.get("tier", "IMPORTANT")))
            confidence = float(item.get("confidence", 0.0))
            reason = str(item.get("reason", "No reason provided"))
            safe_raw = bool(item.get("safe_to_delete", False))

            if tier in (ImportanceTier.CRITICAL, ImportanceTier.IMPORTANT):
                safe_raw = False

            if safe_raw and confidence < CONFIDENCE_THRESHOLD:
                safe_raw = False

            decision = TriageDecision(
                message_id=mid,
                tier=tier,
                safe_to_delete=safe_raw,
                confidence=confidence,
                reason=reason,
                subject=candidate.message.subject,
            )
            decision = self.apply_hard_safety(decision, candidate)
            self._append_log(
                {
                    "message_id": decision.message_id,
                    "tier": decision.tier.value,
                    "safe_to_delete": decision.safe_to_delete,
                    "confidence": decision.confidence,
                    "reason": decision.reason,
                    "kept_by_safety": decision.kept_by_safety,
                    "dry_run": dry_run,
                    "source": "agent",
                    "model": TRIAGE_AGENT_MODEL,
                }
            )
            decisions.append(decision)

        return decisions

    async def classify_all(
        self,
        candidates: list[TriageCandidate],
        *,
        dry_run: bool,
        batch_size: int = DEFAULT_BATCH_SIZE,
        progress_callback: Any | None = None,
    ) -> list[TriageDecision]:
        all_decisions: list[TriageDecision] = []
        total = len(candidates)
        processed = 0

        for start in range(0, total, batch_size):
            batch = candidates[start : start + batch_size]
            decisions = await self.classify_batch(batch, dry_run=dry_run)
            all_decisions.extend(decisions)
            processed = min(start + len(batch), total)
            if progress_callback:
                await progress_callback(processed, total, "classifying")

        return all_decisions
