"""add top_down_analyses and source_url to documents

Revision ID: 037
Revises: 036
Create Date: 2026-05-19
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "037"
down_revision = "036"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("source_url", sa.Text(), nullable=True))
    op.add_column("documents", sa.Column("doc_type", sa.String(50), nullable=True))

    op.create_table(
        "top_down_analyses",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("asset_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("job_id", sa.String(), nullable=True),
        sa.Column("mega_trend", sa.Text(), nullable=False),
        sa.Column("financial_health", sa.Text(), nullable=False),
        sa.Column("swot_strengths", postgresql.JSON(), nullable=False),
        sa.Column("swot_weaknesses", postgresql.JSON(), nullable=False),
        sa.Column("swot_opportunities", postgresql.JSON(), nullable=False),
        sa.Column("swot_threats", postgresql.JSON(), nullable=False),
        sa.Column("verdict", sa.String(10), nullable=False),
        sa.Column("target_price", sa.Numeric(20, 8), nullable=True),
        sa.Column("provider", sa.String(), nullable=False),
        sa.Column("model", sa.String(), nullable=False),
        sa.Column("tokens_in", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("tokens_out", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cost_usd", sa.Numeric(10, 6), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("top_down_analyses")
    op.drop_column("documents", "source_url")
    op.drop_column("documents", "doc_type")
