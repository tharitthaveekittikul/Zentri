"""add platform_configs table

Revision ID: 031
Revises: 030
Create Date: 2026-05-08
"""

from alembic import op
import sqlalchemy as sa

revision = "031"
down_revision = "030"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "platform_configs",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("color", sa.String(length=7), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "name", name="uq_platform_configs_user_name"),
    )
    op.create_index(op.f("ix_platform_configs_user_id"), "platform_configs", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_platform_configs_user_id"), table_name="platform_configs")
    op.drop_table("platform_configs")
