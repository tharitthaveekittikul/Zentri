"""add analysis ai feature tables

Revision ID: 041
Revises: 040
Create Date: 2026-05-21
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "041"
down_revision = "040"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "deep_dive_analyses",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("asset_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("job_id", sa.String, nullable=True),
        sa.Column("business_model", sa.Text, nullable=False),
        sa.Column("moat_edge_type", sa.String(50), nullable=False),
        sa.Column("moat_summary", sa.Text, nullable=False),
        sa.Column("moat_competitors", postgresql.JSON, nullable=False),
        sa.Column("catalysts", postgresql.JSON, nullable=False),
        sa.Column("asymmetry_verdict", sa.String(20), nullable=False),
        sa.Column("asymmetry_floor", sa.Text, nullable=False),
        sa.Column("asymmetry_ceiling", sa.Text, nullable=False),
        sa.Column("asymmetry_reasoning", sa.Text, nullable=False),
        sa.Column("provider", sa.String(30), nullable=False),
        sa.Column("model", sa.String(100), nullable=False),
        sa.Column("tokens_in", sa.Integer, nullable=False, server_default="0"),
        sa.Column("tokens_out", sa.Integer, nullable=False, server_default="0"),
        sa.Column("cost_usd", sa.Numeric(10, 6), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "bear_case_analyses",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("asset_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("job_id", sa.String, nullable=True),
        sa.Column("red_flags", postgresql.JSON, nullable=False),
        sa.Column("summary", sa.Text, nullable=False),
        sa.Column("provider", sa.String(30), nullable=False),
        sa.Column("model", sa.String(100), nullable=False),
        sa.Column("tokens_in", sa.Integer, nullable=False, server_default="0"),
        sa.Column("tokens_out", sa.Integer, nullable=False, server_default="0"),
        sa.Column("cost_usd", sa.Numeric(10, 6), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "peer_comparison_analyses",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("asset_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("job_id", sa.String, nullable=True),
        sa.Column("sector_label", sa.String(100), nullable=False),
        sa.Column("ranked", postgresql.JSON, nullable=False),
        sa.Column("methodology_note", sa.Text, nullable=False),
        sa.Column("provider", sa.String(30), nullable=False),
        sa.Column("model", sa.String(100), nullable=False),
        sa.Column("tokens_in", sa.Integer, nullable=False, server_default="0"),
        sa.Column("tokens_out", sa.Integer, nullable=False, server_default="0"),
        sa.Column("cost_usd", sa.Numeric(10, 6), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "combined_verdicts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("asset_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("job_id", sa.String, nullable=True),
        sa.Column("verdict", sa.String(20), nullable=False),
        sa.Column("conviction", sa.Integer, nullable=False),
        sa.Column("bull_thesis", sa.Text, nullable=False),
        sa.Column("bear_thesis", sa.Text, nullable=False),
        sa.Column("key_risks", postgresql.JSON, nullable=False),
        sa.Column("reasoning", sa.Text, nullable=False),
        sa.Column("based_on", postgresql.JSON, nullable=False),
        sa.Column("provider", sa.String(30), nullable=False),
        sa.Column("model", sa.String(100), nullable=False),
        sa.Column("tokens_in", sa.Integer, nullable=False, server_default="0"),
        sa.Column("tokens_out", sa.Integer, nullable=False, server_default="0"),
        sa.Column("cost_usd", sa.Numeric(10, 6), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("combined_verdicts")
    op.drop_table("peer_comparison_analyses")
    op.drop_table("bear_case_analyses")
    op.drop_table("deep_dive_analyses")
