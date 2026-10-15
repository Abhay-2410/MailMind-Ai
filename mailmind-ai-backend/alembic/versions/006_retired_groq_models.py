"""Move saved AI model preferences off decommissioned Groq Llama models

Revision ID: 006_retired_groq_models
Revises: 005_categorization_signals
Create Date: 2026-10-15
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "006_retired_groq_models"
down_revision: str | None = "005_categorization_signals"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

REPLACEMENTS = {
    "llama-3.1-8b-instant": "openai/gpt-oss-20b",
    "llama-3.3-70b-versatile": "openai/gpt-oss-120b",
}


def upgrade() -> None:
    for old, new in REPLACEMENTS.items():
        op.execute(
            sa.text("UPDATE user_settings SET ai_model = :new WHERE ai_model = :old").bindparams(
                new=new, old=old
            )
        )


def downgrade() -> None:
    # Data-only migration; the old model ids no longer exist upstream.
    pass
