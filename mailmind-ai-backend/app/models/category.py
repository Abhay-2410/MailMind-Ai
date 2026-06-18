import enum
import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Enum, Float, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.email import Email


class EmailCategory(str, enum.Enum):
    IMPORTANT = "important"
    WORK = "work"
    PERSONAL = "personal"
    FINANCE = "finance"
    PROMOTIONS = "promotions"
    SOCIAL = "social"
    UPDATES = "updates"


class Category(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "categories"

    email_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("emails.id", ondelete="CASCADE"),
        unique=True,
        index=True,
        nullable=False,
    )
    category: Mapped[EmailCategory] = mapped_column(
        Enum(
            EmailCategory,
            name="email_category",
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
        index=True,
    )
    confidence: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    model_used: Mapped[str | None] = mapped_column(String(100), nullable=True)

    email: Mapped["Email"] = relationship(back_populates="category")
