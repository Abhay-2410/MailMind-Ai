import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User


@pytest.mark.asyncio
async def test_user_model_persist(db_session: AsyncSession) -> None:
    user = User(email="test@example.com", full_name="Test User")
    db_session.add(user)
    await db_session.commit()

    result = await db_session.execute(select(User).where(User.email == "test@example.com"))
    saved = result.scalar_one()
    assert saved.full_name == "Test User"
    assert saved.is_active is True
