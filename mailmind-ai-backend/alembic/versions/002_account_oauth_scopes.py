"""Add oauth_scopes to accounts

Revision ID: 002_account_oauth_scopes
Revises: 001_initial_schema
Create Date: 2026-06-19
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "002_account_oauth_scopes"
down_revision: str | None = "001_initial_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        sa.text("ALTER TABLE accounts ADD COLUMN IF NOT EXISTS oauth_scopes TEXT")
    )


def downgrade() -> None:
    op.execute(sa.text("ALTER TABLE accounts DROP COLUMN IF EXISTS oauth_scopes"))
