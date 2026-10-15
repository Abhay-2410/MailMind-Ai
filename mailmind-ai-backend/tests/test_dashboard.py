import pytest
from datetime import UTC, datetime
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.account import Account
from app.models.ai_usage import AIActionType, AIUsage
from app.models.category import Category, EmailCategory
from app.models.email import Email
from app.models.user import User
from app.services.dashboard_service import DashboardService


@pytest.mark.asyncio
async def test_dashboard_stats(db_session: AsyncSession) -> None:
    user = User(email="dash@example.com", google_id="g-dash", is_active=True)
    db_session.add(user)
    await db_session.flush()

    account = Account(
        user_id=user.id,
        email="dash@example.com",
        access_token_encrypted="enc",
        is_primary=True,
        is_active=True,
        last_synced_at=datetime.now(UTC),
    )
    db_session.add(account)
    await db_session.flush()

    email1 = Email(
        user_id=user.id,
        account_id=account.id,
        gmail_id="g1",
        sender="a@test.com",
        subject="Important update",
        received_at=datetime.now(UTC),
        is_read=False,
        is_important=True,
        priority_score=75,
    )
    email2 = Email(
        user_id=user.id,
        account_id=account.id,
        gmail_id="g2",
        sender="b@test.com",
        subject="Newsletter",
        received_at=datetime.now(UTC),
        is_read=True,
        is_important=False,
    )
    db_session.add_all([email1, email2])
    await db_session.flush()

    db_session.add(Category(email_id=email1.id, category=EmailCategory.IMPORTANT, confidence=0.9))
    db_session.add(
        AIUsage(
            user_id=user.id,
            action_type=AIActionType.SUMMARIZE,
            model="deepseek/deepseek-chat",
            total_tokens=100,
        )
    )
    await db_session.commit()

    service = DashboardService()
    dashboard = await service.get_dashboard(db_session, user)

    assert dashboard.stats.total_emails == 2
    assert dashboard.stats.unread_emails == 1
    assert dashboard.stats.important_emails == 1
    assert dashboard.stats.ai_actions_saved == 1
    assert dashboard.stats.categorized_emails == 1
    assert len(dashboard.categories) == 2
    assert dashboard.categories[0].category == "important"
    assert dashboard.categories[0].percentage == 50.0
    assert len(dashboard.recent_activity) >= 1


@pytest.mark.asyncio
async def test_dashboard_api(client, db_session: AsyncSession) -> None:
    from app.core.security import create_access_token

    user = User(email="api-dash@example.com", google_id="g-api", is_active=True)
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    token = create_access_token(str(user.id))
    response = await client.get(
        "/api/v1/dashboard",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    body = response.json()
    assert "stats" in body
    assert body["stats"]["total_emails"] == 0
