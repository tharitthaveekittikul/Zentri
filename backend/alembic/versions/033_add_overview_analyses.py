"""add overview_analyses table

Revision ID: 033
Revises: 032
Create Date: 2026-05-09
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "033"
down_revision = "032"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "overview_analyses",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("score", sa.SmallInteger(), nullable=False),
        sa.Column("grade", sa.String(), nullable=False),
        sa.Column("health", sa.String(), nullable=False),
        sa.Column("portfolio_adherence_pct", sa.SmallInteger(), nullable=True),
        sa.Column("insights", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("top_action", sa.Text(), nullable=False),
        sa.Column("provider", sa.String(), nullable=False),
        sa.Column("model", sa.String(), nullable=False),
        sa.Column("tokens_in", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("tokens_out", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cost_usd", sa.Numeric(10, 6), nullable=False, server_default="0"),
        sa.Column("cost_thb", sa.Numeric(10, 4), nullable=False, server_default="0"),
        sa.Column("exchange_rate", sa.Numeric(12, 4), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_overview_analyses_user_id", "overview_analyses", ["user_id"])
    op.create_index(
        "ix_overview_analyses_user_created",
        "overview_analyses",
        ["user_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_overview_analyses_user_created", table_name="overview_analyses")
    op.drop_index("ix_overview_analyses_user_id", table_name="overview_analyses")
    op.drop_table("overview_analyses")
