"""add job status and error_message to analysis tables

Revision ID: 042
Revises: 041
Create Date: 2026-05-21
"""
from alembic import op
import sqlalchemy as sa

revision = "042"
down_revision = "041"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for table in [
        "deep_dive_analyses",
        "bear_case_analyses",
        "peer_comparison_analyses",
        "combined_verdicts",
    ]:
        op.add_column(table, sa.Column("status", sa.String(20), nullable=False, server_default="done"))
        op.add_column(table, sa.Column("error_message", sa.Text(), nullable=True))


def downgrade() -> None:
    for table in [
        "deep_dive_analyses",
        "bear_case_analyses",
        "peer_comparison_analyses",
        "combined_verdicts",
    ]:
        op.drop_column(table, "error_message")
        op.drop_column(table, "status")
