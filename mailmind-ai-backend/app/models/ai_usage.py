import enum
import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Enum, ForeignKey, Integer, String, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.types import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.user import User


class AIActionType(str, enum.Enum):
    SUMMARIZE = "summarize"
    REPLY = "reply"
    CATEGORIZE = "categorize"
    SEARCH = "search"
    ASSISTANT = "assistant"


class AIUsage(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "ai_usage"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    action_type: Mapped[AIActionType] = mapped_column(
        Enum(
            AIActionType,
            name="ai_action_type",
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
        index=True,
    )
    provider: Mapped[str] = mapped_column(String(50), default="openrouter", nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    metadata_json: Mapped[dict | None] = mapped_column(JSON().with_variant(JSONB(), "postgresql"), nullable=True)

    user: Mapped["User"] = relationship(back_populates="ai_usage_records")
