"""add tool_rounds to llm_call_log

Revision ID: 046
Revises: 045
Create Date: 2026-05-26
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "046"
down_revision = "045"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "llm_call_logs",
        sa.Column("tool_rounds", postgresql.JSON(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("llm_call_logs", "tool_rounds")
