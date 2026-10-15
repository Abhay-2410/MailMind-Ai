"""Email classification signals, priority score, category provenance, sender rules, Gmail watch

Revision ID: 005_categorization_signals
Revises: 004_account_gmail_history
Create Date: 2026-10-15

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "005_categorization_signals"
down_revision: str | None = "004_account_gmail_history"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

email_category = postgresql.ENUM(name="email_category", create_type=False)


def upgrade() -> None:
    op.add_column("emails", sa.Column("recipients", sa.Text(), nullable=True))
    op.add_column("emails", sa.Column("list_id", sa.String(length=255), nullable=True))
    op.add_column(
        "emails",
        sa.Column("is_bulk", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column(
        "emails",
        sa.Column("is_automated", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column(
        "emails",
        sa.Column("priority_score", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "emails",
        sa.Column("signals_version", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index("ix_emails_priority_score", "emails", ["priority_score"])
    op.create_index("ix_emails_user_sender", "emails", ["user_id", "sender"])

    op.add_column(
        "categories",
        sa.Column("source", sa.String(length=32), nullable=False, server_default="gmail"),
    )
    op.add_column("categories", sa.Column("reason", sa.String(length=255), nullable=True))
    op.execute(
        sa.text(
            "UPDATE categories SET source = 'ai' "
            "WHERE model_used IS NOT NULL AND model_used <> 'gmail'"
        )
    )

    op.create_table(
        "sender_rules",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sender", sa.String(length=320), nullable=False),
        sa.Column("category", email_category, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "sender", name="uq_sender_rules_user_sender"),
    )
    op.create_index("ix_sender_rules_user_id", "sender_rules", ["user_id"])

    op.add_column(
        "accounts",
        sa.Column("gmail_watch_expires_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("accounts", "gmail_watch_expires_at")
    op.drop_index("ix_sender_rules_user_id", table_name="sender_rules")
    op.drop_table("sender_rules")
    op.drop_column("categories", "reason")
    op.drop_column("categories", "source")
    op.drop_index("ix_emails_user_sender", table_name="emails")
    op.drop_index("ix_emails_priority_score", table_name="emails")
    for column in ("signals_version", "priority_score", "is_automated", "is_bulk", "list_id", "recipients"):
        op.drop_column("emails", column)
