"""add telegram config to users

Revision ID: 015
Revises: 014
Create Date: 2026-05-06
"""

from alembic import op
import sqlalchemy as sa

revision = "015"
down_revision = "014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("telegram_bot_token", sa.Text(), nullable=True))
    op.add_column("users", sa.Column("telegram_chat_id", sa.String(100), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "telegram_chat_id")
    op.drop_column("users", "telegram_bot_token")
