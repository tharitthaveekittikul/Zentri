"""add news_articles table

Revision ID: 034
Revises: 033
Create Date: 2026-05-09
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "034"
down_revision = "033"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "news_articles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("symbol", sa.String(20), nullable=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("url", sa.Text(), nullable=False, unique=True),
        sa.Column("source", sa.String(100), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "fetched_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_news_articles_symbol", "news_articles", ["symbol"])
    op.create_index("ix_news_articles_fetched_at", "news_articles", ["fetched_at"])
    op.create_index("ix_news_articles_symbol_fetched", "news_articles", ["symbol", "fetched_at"])


def downgrade() -> None:
    op.drop_index("ix_news_articles_symbol_fetched", table_name="news_articles")
    op.drop_index("ix_news_articles_fetched_at", table_name="news_articles")
    op.drop_index("ix_news_articles_symbol", table_name="news_articles")
    op.drop_table("news_articles")
