"""universal_import_llm_logging

Revision ID: 006
Revises: 005
Create Date: 2026-05-03 18:09:25.860392

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '006'
down_revision: Union[str, None] = '005'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create llm_call_logs table
    op.create_table(
        'llm_call_logs',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('feature_key', sa.String(length=50), nullable=False),
        sa.Column('provider', sa.String(length=30), nullable=False),
        sa.Column('model', sa.String(length=100), nullable=False),
        sa.Column('prompt_in', sa.Text(), nullable=False),
        sa.Column('response_out', sa.Text(), nullable=False),
        sa.Column('tokens_in', sa.Integer(), nullable=False),
        sa.Column('tokens_out', sa.Integer(), nullable=False),
        sa.Column('cost_usd', sa.Numeric(precision=10, scale=6), nullable=False),
        sa.Column('cost_thb', sa.Numeric(precision=10, scale=6), nullable=False),
        sa.Column('exchange_rate', sa.Numeric(precision=10, scale=4), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_llm_call_logs_created_at'), 'llm_call_logs', ['created_at'], unique=False)
    op.create_index(op.f('ix_llm_call_logs_feature_key'), 'llm_call_logs', ['feature_key'], unique=False)
    op.create_index(op.f('ix_llm_call_logs_user_id'), 'llm_call_logs', ['user_id'], unique=False)

    # 2. Create exchange_rate_cache table
    op.create_table(
        'exchange_rate_cache',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('rate_date', sa.Date(), nullable=False),
        sa.Column('from_currency', sa.String(length=10), nullable=False),
        sa.Column('to_currency', sa.String(length=10), nullable=False),
        sa.Column('rate', sa.Numeric(precision=12, scale=6), nullable=False),
        sa.Column('fetched_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('rate_date', 'from_currency', 'to_currency'),
    )
    op.create_index(op.f('ix_exchange_rate_cache_rate_date'), 'exchange_rate_cache', ['rate_date'], unique=False)

    # 3-5. Add columns to import_templates
    op.add_column('import_templates', sa.Column('value_transforms', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'))
    op.add_column('import_templates', sa.Column('derived_fields', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'))
    op.add_column('import_templates', sa.Column('defaults', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'))

    # Remove server defaults after backfill (leave as JSONB columns)
    op.alter_column('import_templates', 'value_transforms', server_default=None)
    op.alter_column('import_templates', 'derived_fields', server_default=None)
    op.alter_column('import_templates', 'defaults', server_default=None)

    # 6-7. Add currency columns to users
    op.add_column('users', sa.Column('currency_primary', sa.String(length=10), nullable=False, server_default='THB'))
    op.add_column('users', sa.Column('currency_secondary', sa.String(length=10), nullable=False, server_default='USD'))

    op.alter_column('users', 'currency_primary', server_default=None)
    op.alter_column('users', 'currency_secondary', server_default=None)


def downgrade() -> None:
    op.drop_column('users', 'currency_secondary')
    op.drop_column('users', 'currency_primary')

    op.drop_column('import_templates', 'defaults')
    op.drop_column('import_templates', 'derived_fields')
    op.drop_column('import_templates', 'value_transforms')

    op.drop_index(op.f('ix_exchange_rate_cache_rate_date'), table_name='exchange_rate_cache')
    op.drop_table('exchange_rate_cache')

    op.drop_index(op.f('ix_llm_call_logs_user_id'), table_name='llm_call_logs')
    op.drop_index(op.f('ix_llm_call_logs_feature_key'), table_name='llm_call_logs')
    op.drop_index(op.f('ix_llm_call_logs_created_at'), table_name='llm_call_logs')
    op.drop_table('llm_call_logs')
