"""simplify_import_remove_platforms

Revision ID: 007
Revises: 006
Create Date: 2026-05-04
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '007'
down_revision: Union[str, None] = '006'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Drop import_templates (has FK to platforms — must go before platforms)
    op.drop_table('import_templates')

    # 2. Drop import_profiles
    op.execute("DROP TABLE IF EXISTS import_profiles")

    # 3. Drop platform_id FK + column from transactions
    op.drop_constraint('transactions_platform_id_fkey', 'transactions', type_='foreignkey')
    op.drop_column('transactions', 'platform_id')

    # 4. Add platform text column to transactions
    op.add_column('transactions', sa.Column('platform', sa.String(100), nullable=True))

    # 5. Extend transaction_type_enum (pg16 supports ADD VALUE in transaction)
    op.execute("ALTER TYPE transaction_type_enum ADD VALUE IF NOT EXISTS 'reward'")
    op.execute("ALTER TYPE transaction_type_enum ADD VALUE IF NOT EXISTS 'fee'")
    op.execute("ALTER TYPE transaction_type_enum ADD VALUE IF NOT EXISTS 'transfer'")

    # 6. Add purchased_at to holdings
    op.add_column('holdings', sa.Column('purchased_at', sa.Date(), nullable=True))

    # 7. Drop platforms table (all FKs to it are now gone)
    op.drop_table('platforms')


def downgrade() -> None:
    op.create_table(
        'platforms',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('asset_types_supported', postgresql.JSONB(), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.drop_column('holdings', 'purchased_at')
    op.drop_column('transactions', 'platform')
    op.add_column('transactions', sa.Column('platform_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        'transactions_platform_id_fkey', 'transactions', 'platforms', ['platform_id'], ['id']
    )
