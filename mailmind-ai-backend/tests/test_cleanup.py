import pytest
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.account import Account
from app.models.user import User
from app.schemas.cleanup import CleanupAnalyzeRequest, CleanupDeleteRequest, SmartCleanupCategory
from app.services.cleanup_service import CleanupService
from app.utils.encryption import encrypt_token


@pytest.mark.asyncio
async def test_cleanup_counts(db_session: AsyncSession) -> None:
    user = User(email="cleanup@example.com", google_id="g-clean", is_active=True)
    db_session.add(user)
    await db_session.flush()

    account = Account(
        user_id=user.id,
        email="cleanup@example.com",
        access_token_encrypted=encrypt_token("access-token"),
        refresh_token_encrypted=encrypt_token("refresh-token"),
        token_expires_at=datetime.now(UTC) + timedelta(hours=1),
        is_primary=True,
        is_active=True,
    )
    db_session.add(account)
    await db_session.commit()
    await db_session.refresh(user)

    mock_helpers = AsyncMock()
    mock_helpers.count_category_messages = AsyncMock(return_value=42)

    service = CleanupService(helpers=mock_helpers)
    result = await service.get_counts(db_session, user)

    assert len(result.categories) == 4
    assert result.categories[0].count == 42


@pytest.mark.asyncio
async def test_cleanup_heuristic_analyze(db_session: AsyncSession) -> None:
    user = User(email="analyze@example.com", google_id="g-analyze", is_active=True)
    db_session.add(user)
    await db_session.flush()

    account = Account(
        user_id=user.id,
        email="analyze@example.com",
        access_token_encrypted=encrypt_token("access-token"),
        refresh_token_encrypted=encrypt_token("refresh-token"),
        token_expires_at=datetime.now(UTC) + timedelta(hours=1),
        is_primary=True,
        is_active=True,
    )
    db_session.add(account)
    await db_session.commit()
    await db_session.refresh(user)

    mock_helpers = AsyncMock()
    mock_helpers.collect_category_message_ids = AsyncMock(return_value=["m1", "m2", "m3"])
    from types import SimpleNamespace

    candidate = SimpleNamespace(
        message=SimpleNamespace(gmail_id="m1", subject="Promo A"),
    )
    mock_helpers.filter_heuristic_candidates = AsyncMock(
        return_value=([candidate], ["m2", "m3"]),
    )
    mock_helpers.fetch_contact_emails = AsyncMock(return_value=set())

    mock_gmail = AsyncMock()
    mock_gmail.ensure_valid_access_token = AsyncMock(return_value="access-token")

    service = CleanupService(gmail_service=mock_gmail, helpers=mock_helpers)
    result = await service.analyze(
        db_session,
        user,
        CleanupAnalyzeRequest(category=SmartCleanupCategory.PROMOTIONS, dry_run=True),
    )

    assert result.delete_count == 1
    assert result.kept_count == 2
    assert result.message_ids == ["m1"]


@pytest.mark.asyncio
async def test_cleanup_trash_delete(db_session: AsyncSession) -> None:
    user = User(email="delete@example.com", google_id="g-del", is_active=True)
    db_session.add(user)
    await db_session.flush()

    account = Account(
        user_id=user.id,
        email="delete@example.com",
        access_token_encrypted=encrypt_token("access-token"),
        refresh_token_encrypted=encrypt_token("refresh-token"),
        token_expires_at=datetime.now(UTC) + timedelta(hours=1),
        is_primary=True,
        is_active=True,
    )
    db_session.add(account)
    await db_session.commit()
    await db_session.refresh(user)

    mock_helpers = AsyncMock()
    mock_helpers.trash_messages = AsyncMock(return_value=(2, []))

    mock_gmail = AsyncMock()
    mock_gmail.ensure_access_token_for_delete = AsyncMock(return_value="access-token")

    service = CleanupService(gmail_service=mock_gmail, helpers=mock_helpers)
    result = await service.delete_messages(
        db_session,
        user,
        CleanupDeleteRequest(message_ids=["m1", "m2"], permanent=False),
    )

    assert result.deleted == 2
    assert result.trashed is True
    mock_helpers.trash_messages.assert_awaited_once_with("access-token", ["m1", "m2"])


@pytest.mark.asyncio
async def test_primary_agent_safety_rules() -> None:
    from app.agents.primary_inbox_agent import PrimaryInboxAgent
    from app.utils.gmail_cleanup_helpers import CleanupCandidate, ThreadInfo
    from app.services.gmail_service import GmailMessage

    agent = PrimaryInboxAgent()
    message = GmailMessage(
        gmail_id="x1",
        thread_id="t1",
        sender="bot@example.com",
        sender_name="Bot",
        subject="Test",
        preview="hello",
        body_text="hello",
        body_html=None,
        received_at=datetime.now(UTC) - timedelta(days=60),
        is_read=True,
        is_starred=True,
        is_important=False,
        labels=["INBOX"],
    )
    candidate = CleanupCandidate(
        message=message,
        thread=ThreadInfo(thread_id="t1", message_count=1, has_user_reply=False),
        has_attachment=False,
    )

    with patch.object(agent, "_append_log"):
        decision = await agent.evaluate_candidate(candidate, dry_run=True)

    assert decision.decision == "keep"
    assert decision.kept_by_safety is True


@pytest.mark.asyncio
async def test_triage_analyze_builds_summary(db_session: AsyncSession) -> None:
    from app.agents.inbox_triage_agent import ImportanceTier as AgentTier, TriageDecision
    from app.utils.gmail_cleanup_helpers import ThreadInfo
    from app.services.gmail_service import GmailMessage
    from app.utils.gmail_pagination_helpers import TriageCandidate

    user = User(email="triage@example.com", google_id="g-triage", is_active=True)
    db_session.add(user)
    await db_session.flush()

    account = Account(
        user_id=user.id,
        email="triage@example.com",
        access_token_encrypted=encrypt_token("access-token"),
        refresh_token_encrypted=encrypt_token("refresh-token"),
        token_expires_at=datetime.now(UTC) + timedelta(hours=1),
        is_primary=True,
        is_active=True,
    )
    db_session.add(account)
    await db_session.commit()
    await db_session.refresh(user)

    message = GmailMessage(
        gmail_id="m-low",
        thread_id="t1",
        sender="promo@shop.com",
        sender_name="Shop",
        subject="Old promo",
        preview="sale ends",
        body_text="sale ends",
        body_html=None,
        received_at=datetime.now(UTC) - timedelta(days=90),
        is_read=True,
        is_starred=False,
        is_important=False,
        labels=["INBOX", "CATEGORY_PROMOTIONS"],
    )
    candidate = TriageCandidate(
        message=message,
        thread=ThreadInfo(thread_id="t1", message_count=1, has_user_reply=False),
        has_attachment=False,
        sender_domain="shop.com",
        sender_in_contacts=False,
        user_replied_to_sender=False,
    )
    decisions = [
        TriageDecision(
            message_id="m-low",
            tier=AgentTier.LOW_VALUE,
            safe_to_delete=True,
            confidence=0.95,
            reason="Expired promo",
            subject="Old promo",
        ),
        TriageDecision(
            message_id="m-crit",
            tier=AgentTier.CRITICAL,
            safe_to_delete=False,
            confidence=0.99,
            reason="Bank alert",
            subject="Statement ready",
        ),
    ]

    mock_pagination = AsyncMock()
    mock_pagination.collect_full_inbox_message_ids = AsyncMock(return_value=["m-low", "m-crit"])
    mock_pagination.build_triage_candidates = AsyncMock(return_value=[candidate])

    mock_triage_agent = AsyncMock()
    mock_triage_agent.classify_all = AsyncMock(return_value=decisions)

    mock_gmail = AsyncMock()
    mock_gmail.ensure_valid_access_token = AsyncMock(return_value="access-token")

    service = CleanupService(
        gmail_service=mock_gmail,
        triage_agent=mock_triage_agent,
        pagination=mock_pagination,
    )
    from app.schemas.cleanup import TriageAnalyzeRequest

    result = await service.analyze_triage(
        db_session,
        user,
        TriageAnalyzeRequest(dry_run=True),
    )

    assert result.total_scanned == 2
    assert result.low_value == 1
    assert result.critical == 1
    assert result.classifications["m-low"].safe_to_delete is True


@pytest.mark.asyncio
async def test_triage_delete_only_safe_tier(db_session: AsyncSession) -> None:
    from app.agents.inbox_triage_agent import ImportanceTier as AgentTier, TriageDecision
    from app.utils.gmail_cleanup_helpers import ThreadInfo
    from app.services.gmail_service import GmailMessage
    from app.utils.gmail_pagination_helpers import TriageCandidate
    from app.services.triage_jobs import triage_job_store
    from app.schemas.cleanup import TriageDeleteRequest, TriageDeleteTier

    user = User(email="triage-del@example.com", google_id="g-triage-del", is_active=True)
    db_session.add(user)
    await db_session.flush()

    account = Account(
        user_id=user.id,
        email="triage-del@example.com",
        access_token_encrypted=encrypt_token("access-token"),
        refresh_token_encrypted=encrypt_token("refresh-token"),
        token_expires_at=datetime.now(UTC) + timedelta(hours=1),
        is_primary=True,
        is_active=True,
    )
    db_session.add(account)
    await db_session.commit()
    await db_session.refresh(user)

    def make_candidate(mid: str) -> TriageCandidate:
        message = GmailMessage(
            gmail_id=mid,
            thread_id="t1",
            sender="promo@shop.com",
            sender_name="Shop",
            subject=f"Subject {mid}",
            preview="body",
            body_text="body",
            body_html=None,
            received_at=datetime.now(UTC) - timedelta(days=90),
            is_read=True,
            is_starred=False,
            is_important=False,
            labels=["INBOX"],
        )
        return TriageCandidate(
            message=message,
            thread=ThreadInfo(thread_id="t1", message_count=1, has_user_reply=False),
            has_attachment=False,
            sender_domain="shop.com",
            sender_in_contacts=False,
            user_replied_to_sender=False,
        )

    decisions = [
        TriageDecision(
            message_id="safe1",
            tier=AgentTier.DISPOSABLE,
            safe_to_delete=True,
            confidence=0.95,
            reason="Marketing",
            subject="Ad",
        ),
        TriageDecision(
            message_id="critical1",
            tier=AgentTier.CRITICAL,
            safe_to_delete=False,
            confidence=0.99,
            reason="Important",
            subject="Bank",
        ),
    ]
    candidates = [make_candidate("safe1"), make_candidate("critical1")]
    triage_job_store.save_session(user.id, decisions, candidates)

    mock_helpers = AsyncMock()
    mock_helpers.trash_messages = AsyncMock(return_value=(1, []))

    mock_gmail = AsyncMock()
    mock_gmail.ensure_access_token_for_delete = AsyncMock(return_value="access-token")

    service = CleanupService(gmail_service=mock_gmail, helpers=mock_helpers)
    result = await service.delete_triage_tier(
        db_session,
        user,
        TriageDeleteRequest(tier=TriageDeleteTier.DISPOSABLE),
    )

    assert result.deleted == 1
    mock_helpers.trash_messages.assert_awaited_once_with("access-token", ["safe1"])
