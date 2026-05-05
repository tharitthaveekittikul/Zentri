"""add unique constraint to watchlist_items (user_id, asset_id)

Revision ID: 016
Revises: 015
Create Date: 2026-05-06
"""

from alembic import op

revision = "016"
down_revision = "015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_watchlist_user_asset",
        "watchlist_items",
        ["user_id", "asset_id"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_watchlist_user_asset", "watchlist_items", type_="unique")
