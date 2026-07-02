"""add dark theme preference

Revision ID: 003_add_dark_theme
Revises: 002_account_oauth_scopes
Create Date: 2026-06-17

"""

from collections.abc import Sequence

from alembic import op

revision: str = "003_add_dark_theme"
down_revision: str | None = "002_account_oauth_scopes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TYPE theme_preference ADD VALUE IF NOT EXISTS 'dark'")


def downgrade() -> None:
    pass
