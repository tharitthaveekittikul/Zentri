"""add price targets to combined_verdicts

Revision ID: 043
Revises: 042
Create Date: 2026-05-21
"""
from alembic import op
import sqlalchemy as sa

revision = "043"
down_revision = "042"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("combined_verdicts", sa.Column("entry_price", sa.Numeric(12, 2), nullable=True))
    op.add_column("combined_verdicts", sa.Column("target_price", sa.Numeric(12, 2), nullable=True))
    op.add_column("combined_verdicts", sa.Column("stop_loss", sa.Numeric(12, 2), nullable=True))
    op.add_column("combined_verdicts", sa.Column("risk_reward", sa.Numeric(6, 2), nullable=True))


def downgrade() -> None:
    op.drop_column("combined_verdicts", "risk_reward")
    op.drop_column("combined_verdicts", "stop_loss")
    op.drop_column("combined_verdicts", "target_price")
    op.drop_column("combined_verdicts", "entry_price")
