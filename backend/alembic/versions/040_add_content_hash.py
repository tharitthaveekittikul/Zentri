"""add content_hash to documents

Revision ID: 040
Revises: 039
Create Date: 2026-05-21
"""
from alembic import op
import sqlalchemy as sa

revision = "040"
down_revision = "039"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "documents",
        sa.Column("content_hash", sa.String(64), nullable=True),
    )
    op.create_index(
        "ix_documents_content_hash_unique",
        "documents",
        ["content_hash"],
        unique=True,
        postgresql_where=sa.text("content_hash IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_documents_content_hash_unique", table_name="documents")
    op.drop_column("documents", "content_hash")
