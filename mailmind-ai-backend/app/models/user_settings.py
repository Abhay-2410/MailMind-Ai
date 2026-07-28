import enum
import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Enum, ForeignKey, String, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.types import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.user import User

JSONDict = JSON().with_variant(JSONB(), "postgresql")


class ThemePreference(str, enum.Enum):
    LIGHT = "light"
    DARK = "dark"
    SYSTEM = "system"


class UserSettings(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "user_settings"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        index=True,
        nullable=False,
    )

    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    timezone: Mapped[str] = mapped_column(String(64), default="UTC", nullable=False)

    ai_provider: Mapped[str] = mapped_column(String(50), default="groq", nullable=False)
    ai_model: Mapped[str] = mapped_column(String(100), default="llama-3.1-8b-instant", nullable=False)

    theme: Mapped[ThemePreference] = mapped_column(
        Enum(
            ThemePreference,
            name="theme_preference",
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        default=ThemePreference.LIGHT,
        nullable=False,
    )

    security_preferences: Mapped[dict | None] = mapped_column(JSONDict, nullable=True)
    notification_preferences: Mapped[dict | None] = mapped_column(JSONDict, nullable=True)

    user: Mapped["User"] = relationship(back_populates="settings")
