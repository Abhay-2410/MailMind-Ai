"""Add gmail_history_id for real-time incremental sync

Revision ID: 004_account_gmail_history
Revises: 003_add_dark_theme
Create Date: 2026-07-27

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "004_account_gmail_history"
down_revision: str | None = "003_add_dark_theme"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        sa.text("ALTER TABLE accounts ADD COLUMN IF NOT EXISTS gmail_history_id VARCHAR(64)")
    )


def downgrade() -> None:
    op.execute(sa.text("ALTER TABLE accounts DROP COLUMN IF EXISTS gmail_history_id"))
