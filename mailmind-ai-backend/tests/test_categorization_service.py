from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.account import Account
from app.models.category import Category, CategorySource, EmailCategory, SenderRule
from app.models.email import Email
from app.models.user import User
from app.services.categorization_service import CategorizationService
from app.utils.encryption import encrypt_token


async def _setup(db: AsyncSession) -> tuple[User, list[Email]]:
    user = User(email="me@example.com", google_id="g-cat", is_active=True)
    db.add(user)
    await db.flush()
    account = Account(
        user_id=user.id,
        email="me@example.com",
        access_token_encrypted=encrypt_token("token"),
        is_primary=True,
        is_active=True,
    )
    db.add(account)
    await db.flush()

    emails = [
        Email(
            user_id=user.id,
            account_id=account.id,
            gmail_id=f"m{index}",
            thread_id=f"t{index}",
            sender="news@shop.com",
            subject=f"Big sale {index}",
            received_at=datetime.now(UTC),
            labels='["INBOX", "CATEGORY_PROMOTIONS"]',
            is_bulk=True,
        )
        for index in range(3)
    ]
    db.add_all(emails)
    await db.commit()
    return user, emails


@pytest.mark.asyncio
async def test_deterministic_pass_categorizes_and_scores(db_session: AsyncSession) -> None:
    user, emails = await _setup(db_session)
    service = CategorizationService()
    changed = await service.classify_emails(db_session, user, emails)
    await db_session.commit()

    assert changed == 3
    rows = (await db_session.execute(select(Category))).scalars().all()
    assert {row.category for row in rows} == {EmailCategory.PROMOTIONS}
    assert all(row.source == CategorySource.RULE.value for row in rows)
    assert all(email.priority_score < 60 for email in emails)


@pytest.mark.asyncio
async def test_user_correction_pins_sender_and_survives_reclassification(db_session: AsyncSession) -> None:
    user, emails = await _setup(db_session)
    service = CategorizationService()
    await service.classify_emails(db_session, user, emails)
    await db_session.commit()

    _email, updated = await service.set_user_category(
        db_session, user, emails[0].id, EmailCategory.UPDATES, apply_to_sender=True
    )
    assert updated == 2

    rule = (await db_session.execute(select(SenderRule))).scalar_one()
    assert rule.sender == "news@shop.com"
    assert rule.category == EmailCategory.UPDATES

    await service.classify_emails(db_session, user, emails)
    await db_session.commit()
    rows = {
        row.email_id: row for row in (await db_session.execute(select(Category))).scalars().all()
    }
    assert rows[emails[0].id].source == CategorySource.USER.value
    assert rows[emails[1].id].source == CategorySource.SENDER_RULE.value
    assert {row.category for row in rows.values()} == {EmailCategory.UPDATES}
