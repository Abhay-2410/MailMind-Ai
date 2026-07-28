from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.models import get_default_model_id, get_model_by_id
from app.core.exceptions import AppError
from app.models.account import Account
from app.models.user import User
from app.models.user_settings import ThemePreference as DBThemePreference
from app.models.user_settings import UserSettings
from app.schemas.settings import (
    AccountSummary,
    SettingsResponse,
    ThemePreference,
    UpdateSettingsRequest,
)


class SettingsService:
    async def _get_or_create_settings(
        self,
        db: AsyncSession,
        user: User,
    ) -> UserSettings:
        result = await db.execute(select(UserSettings).where(UserSettings.user_id == user.id))
        settings = result.scalar_one_or_none()
        if settings is None:
            default_model_id = get_default_model_id()
            default_model = get_model_by_id(default_model_id)
            settings = UserSettings(
                user_id=user.id,
                ai_model=default_model_id,
                ai_provider=default_model.provider.value if default_model else "groq",
            )
            db.add(settings)
            await db.flush()
        return settings

    async def get_settings(self, db: AsyncSession, user: User) -> SettingsResponse:
        settings = await self._get_or_create_settings(db, user)

        account_result = await db.execute(
            select(Account)
            .where(Account.user_id == user.id)
            .order_by(Account.is_primary.desc(), Account.created_at.asc())
        )
        accounts = account_result.scalars().all()

        return SettingsResponse(
            user_id=user.id,
            email=user.email,
            full_name=user.full_name,
            avatar_url=user.avatar_url,
            display_name=settings.display_name,
            timezone=settings.timezone,
            ai_provider=settings.ai_provider,
            ai_model=settings.ai_model,
            theme=ThemePreference(settings.theme.value),
            google_connected=any(account.is_active for account in accounts),
            accounts=[AccountSummary.model_validate(account) for account in accounts],
        )

    async def update_settings(
        self,
        db: AsyncSession,
        user: User,
        payload: UpdateSettingsRequest,
    ) -> SettingsResponse:
        settings = await self._get_or_create_settings(db, user)
        data = payload.model_dump(exclude_unset=True)

        if "full_name" in data:
            user.full_name = data.pop("full_name")

        if "ai_model" in data and data["ai_model"] is not None:
            if get_model_by_id(data["ai_model"]) is None:
                raise AppError("Invalid AI model selected", status_code=400)

        if "theme" in data and data["theme"] is not None:
            settings.theme = DBThemePreference(data["theme"].value)

        for field in ("display_name", "timezone", "ai_provider", "ai_model"):
            if field in data:
                setattr(settings, field, data[field])

        await db.commit()
        await db.refresh(user)
        await db.refresh(settings)
        return await self.get_settings(db, user)

    async def list_accounts(self, db: AsyncSession, user_id: UUID) -> list[AccountSummary]:
        result = await db.execute(
            select(Account)
            .where(Account.user_id == user_id)
            .order_by(Account.is_primary.desc(), Account.created_at.asc())
        )
        return [AccountSummary.model_validate(account) for account in result.scalars().all()]
