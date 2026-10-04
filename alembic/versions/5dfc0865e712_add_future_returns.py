"""add future returns

Revision ID: 5dfc0865e712
Revises: e9e24f0aa631
Create Date: 2026-10-03 21:04:23.175737

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = '5dfc0865e712'
down_revision: Union[str, Sequence[str], None] = 'e9e24f0aa631'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.create_table(
        'future_returns',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('company_id', sa.BigInteger(), nullable=False),
        sa.Column('trade_date', sa.Date(), nullable=False),
        sa.Column('close_price', sa.Float(), nullable=True),
        sa.Column('close_5d', sa.Float(), nullable=True),
        sa.Column('close_20d', sa.Float(), nullable=True),
        sa.Column('close_60d', sa.Float(), nullable=True),
        sa.Column('forward_5d_return', sa.Float(), nullable=True),
        sa.Column('forward_20d_return', sa.Float(), nullable=True),
        sa.Column('forward_60d_return', sa.Float(), nullable=True),
        sa.Column('calculation_method', sa.String(), nullable=True),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('CURRENT_TIMESTAMP'),
            nullable=False,
        ),
        sa.Column(
            'updated_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('CURRENT_TIMESTAMP'),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('company_id', 'trade_date', name='uq_future_returns_company_trade_date'),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'],),
    )
    op.create_index('ix_future_returns_company_trade_date', 'future_returns', ['company_id', 'trade_date'],)

def downgrade() -> None:
    op.drop_index('ix_future_returns_company_trade_date', table_name='future_returns')
    op.drop_table('future_returns')
