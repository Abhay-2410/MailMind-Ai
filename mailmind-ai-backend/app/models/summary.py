import enum
import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Enum, ForeignKey, String, Text, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.types import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.email import Email

JSONList = JSON().with_variant(JSONB(), "postgresql")


class PriorityLevel(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class Summary(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "summaries"

    email_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("emails.id", ondelete="CASCADE"),
        unique=True,
        index=True,
        nullable=False,
    )
    key_points: Mapped[list[str]] = mapped_column(JSONList, nullable=False, default=list)
    action_items: Mapped[list[str]] = mapped_column(JSONList, nullable=False, default=list)
    important_dates: Mapped[list[str]] = mapped_column(JSONList, nullable=False, default=list)
    priority_level: Mapped[PriorityLevel] = mapped_column(
        Enum(
            PriorityLevel,
            name="priority_level",
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        default=PriorityLevel.MEDIUM,
        nullable=False,
    )
    summary_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    model_used: Mapped[str | None] = mapped_column(String(100), nullable=True)

    email: Mapped["Email"] = relationship(back_populates="summary")
