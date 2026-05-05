"""backfill platform and purchased_at on holdings from transactions

Revision ID: 012
Revises: 011
Create Date: 2026-05-05
"""
from alembic import op

revision = "012"
down_revision = "011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        WITH earliest AS (
            SELECT
                user_id,
                asset_id,
                MIN(executed_at)::date                                      AS first_date,
                (array_agg(platform ORDER BY executed_at)
                    FILTER (WHERE platform IS NOT NULL))[1]                 AS first_platform
            FROM transactions
            WHERE type IN ('buy', 'reward')
            GROUP BY user_id, asset_id
        )
        UPDATE holdings h
        SET
            purchased_at = COALESCE(h.purchased_at, e.first_date),
            platform     = COALESCE(h.platform,     e.first_platform)
        FROM earliest e
        WHERE h.user_id  = e.user_id
          AND h.asset_id = e.asset_id
          AND (h.purchased_at IS NULL OR h.platform IS NULL)
    """)


def downgrade() -> None:
    pass
