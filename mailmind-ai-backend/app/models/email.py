import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.account import Account
    from app.models.category import Category
    from app.models.summary import Summary
    from app.models.user import User


class Email(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "emails"
    __table_args__ = (UniqueConstraint("account_id", "gmail_id", name="uq_emails_account_gmail_id"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("accounts.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    gmail_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    thread_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)

    sender: Mapped[str] = mapped_column(String(320), nullable=False, index=True)
    sender_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    subject: Mapped[str] = mapped_column(String(998), nullable=False, default="")
    preview: Mapped[str | None] = mapped_column(Text, nullable=True)
    body_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    body_html: Mapped[str | None] = mapped_column(Text, nullable=True)

    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    is_starred: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_important: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    labels: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Classification signals parsed from headers (see GmailService.parse_message).
    recipients: Mapped[str | None] = mapped_column(Text, nullable=True)
    list_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_bulk: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_automated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    priority_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False, index=True)
    # Rows below SIGNALS_VERSION are re-fetched from Gmail on the next full sync.
    signals_version: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    account: Mapped["Account"] = relationship(back_populates="emails")
    summary: Mapped["Summary | None"] = relationship(
        back_populates="email",
        cascade="all, delete-orphan",
        uselist=False,
    )
    category: Mapped["Category | None"] = relationship(
        back_populates="email",
        cascade="all, delete-orphan",
        uselist=False,
    )
