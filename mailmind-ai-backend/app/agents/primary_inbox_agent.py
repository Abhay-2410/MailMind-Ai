"""High-precision Primary inbox triage agent (Groq by default, OpenRouter Claude fallback)."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.ai.openrouter import get_provider
from app.core.config import Settings, get_settings
from app.core.exceptions import AppError
from app.utils.ai_json import parse_ai_json
from app.utils.gmail_cleanup_helpers import CleanupCandidate, message_is_old_enough, snippet_preview

logger = logging.getLogger(__name__)

GROQ_PRIMARY_MODEL = "llama-3.3-70b-versatile"
OPENROUTER_PRIMARY_MODEL = "anthropic/claude-sonnet-4-6"
CONFIDENCE_THRESHOLD = 0.95
PRIMARY_AGE_DAYS = 30

SYSTEM_PROMPT = """You are an email triage expert. Decide if a Primary inbox email can be safely permanently deleted. Be EXTREMELY conservative — when in doubt, always say KEEP.

Only recommend DELETE if ALL of the following are true:
- Clearly automated (OTP, receipt, shipping notification, system alert)
- Older than 30 days
- No replies from the user in the thread
- Not from a bank, employer, school, or government sender
- Zero actionable content remaining

Respond ONLY in this JSON format:
{ "decision": "keep" | "delete", "confidence": 0.0–1.0, "reason": "one sentence" }"""

BACKEND_ROOT = Path(__file__).resolve().parents[2]
CLEANUP_LOG_PATH = BACKEND_ROOT / "cleanup_log.json"


@dataclass
class AgentDecision:
    message_id: str
    decision: str
    confidence: float
    reason: str
    kept_by_safety: bool = False


class PrimaryInboxAgent:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        if self.settings.GROQ_API_KEY:
            self.provider_name = "groq"
            self.model_id = GROQ_PRIMARY_MODEL
        else:
            self.provider_name = "openrouter"
            self.model_id = OPENROUTER_PRIMARY_MODEL
        self.provider = get_provider(self.provider_name, self.settings)

    def _append_log(self, entry: dict[str, Any]) -> None:
        entry["logged_at"] = datetime.now(UTC).isoformat()
        try:
            existing: list[Any] = []
            if CLEANUP_LOG_PATH.exists():
                raw = CLEANUP_LOG_PATH.read_text(encoding="utf-8").strip()
                if raw:
                    existing = json.loads(raw)
                    if not isinstance(existing, list):
                        existing = [existing]
            existing.append(entry)
            CLEANUP_LOG_PATH.write_text(json.dumps(existing, indent=2), encoding="utf-8")
        except (OSError, json.JSONDecodeError, TypeError) as exc:
            logger.warning("Failed to write cleanup_log.json: %s", exc)

    def _build_user_prompt(self, candidate: CleanupCandidate) -> str:
        message = candidate.message
        snippet = snippet_preview(message.body_text or message.preview, 500)
        return json.dumps(
            {
                "subject": message.subject,
                "sender_email": message.sender,
                "sender_name": message.sender_name,
                "body_snippet": snippet,
                "thread_message_count": candidate.thread.message_count,
                "received_at": message.received_at.isoformat(),
                "labels": message.labels,
                "has_attachment": candidate.has_attachment,
                "user_replied_in_thread": candidate.thread.has_user_reply,
            },
            ensure_ascii=False,
        )

    async def evaluate_candidate(
        self,
        candidate: CleanupCandidate,
        *,
        dry_run: bool,
        contacts: set[str] | None = None,
        contacts_available: bool = False,
    ) -> AgentDecision:
        message = candidate.message

        if message.is_starred or message.is_important:
            decision = AgentDecision(
                message_id=message.gmail_id,
                decision="keep",
                confidence=1.0,
                reason="Starred or important label",
                kept_by_safety=True,
            )
            self._append_log({**decision.__dict__, "dry_run": dry_run, "source": "safety_rule"})
            return decision

        if candidate.has_attachment:
            decision = AgentDecision(
                message_id=message.gmail_id,
                decision="keep",
                confidence=1.0,
                reason="Has attachment",
                kept_by_safety=True,
            )
            self._append_log({**decision.__dict__, "dry_run": dry_run, "source": "safety_rule"})
            return decision

        if candidate.thread.message_count > 1:
            decision = AgentDecision(
                message_id=message.gmail_id,
                decision="keep",
                confidence=1.0,
                reason="Multi-message thread",
                kept_by_safety=True,
            )
            self._append_log({**decision.__dict__, "dry_run": dry_run, "source": "safety_rule"})
            return decision

        if candidate.thread.has_user_reply:
            decision = AgentDecision(
                message_id=message.gmail_id,
                decision="keep",
                confidence=1.0,
                reason="User replied in thread",
                kept_by_safety=True,
            )
            self._append_log({**decision.__dict__, "dry_run": dry_run, "source": "safety_rule"})
            return decision

        if contacts_available and contacts and message.sender.lower() in contacts:
            decision = AgentDecision(
                message_id=message.gmail_id,
                decision="keep",
                confidence=1.0,
                reason="Sender in Google Contacts",
                kept_by_safety=True,
            )
            self._append_log({**decision.__dict__, "dry_run": dry_run, "source": "safety_rule"})
            return decision

        if not message_is_old_enough(message.received_at, days=PRIMARY_AGE_DAYS):
            decision = AgentDecision(
                message_id=message.gmail_id,
                decision="keep",
                confidence=1.0,
                reason="Not older than 30 days",
                kept_by_safety=True,
            )
            self._append_log({**decision.__dict__, "dry_run": dry_run, "source": "safety_rule"})
            return decision

        try:
            result = await self.provider.complete_json(
                model=self.model_id,
                system_prompt=SYSTEM_PROMPT,
                user_prompt=self._build_user_prompt(candidate),
                temperature=0.1,
                max_tokens=256,
            )
            payload = parse_ai_json(result.content)
        except AppError as exc:
            logger.warning("Primary agent failed for %s: %s", message.gmail_id, exc.message)
            decision = AgentDecision(
                message_id=message.gmail_id,
                decision="keep",
                confidence=0.0,
                reason="Agent unavailable — kept by default",
                kept_by_safety=True,
            )
            self._append_log({**decision.__dict__, "dry_run": dry_run, "source": "agent_error"})
            return decision

        raw_decision = str(payload.get("decision", "keep")).lower()
        confidence = float(payload.get("confidence", 0.0))
        reason = str(payload.get("reason", "No reason provided"))

        if raw_decision != "delete" or confidence < CONFIDENCE_THRESHOLD:
            raw_decision = "keep"

        decision = AgentDecision(
            message_id=message.gmail_id,
            decision=raw_decision,
            confidence=confidence,
            reason=reason,
        )
        self._append_log(
            {
                **decision.__dict__,
                "dry_run": dry_run,
                "source": "agent",
                "model": self.model_id,
            }
        )
        return decision

    async def analyze_candidates(
        self,
        candidates: list[CleanupCandidate],
        *,
        dry_run: bool,
        contacts: set[str] | None = None,
        contacts_available: bool = False,
        progress_callback: Any | None = None,
    ) -> list[AgentDecision]:
        decisions: list[AgentDecision] = []
        total = len(candidates)
        for index, candidate in enumerate(candidates):
            decision = await self.evaluate_candidate(
                candidate,
                dry_run=dry_run,
                contacts=contacts,
                contacts_available=contacts_available,
            )
            decisions.append(decision)
            if progress_callback:
                await progress_callback(index + 1, total)
        return decisions

    @staticmethod
    def deletable_ids(decisions: list[AgentDecision]) -> list[str]:
        return [
            d.message_id
            for d in decisions
            if d.decision == "delete" and d.confidence >= CONFIDENCE_THRESHOLD
        ]
