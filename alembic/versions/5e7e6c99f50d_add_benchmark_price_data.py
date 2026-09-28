"""Add benchmark price data

Revision ID: 5e7e6c99f50d
Revises: 0003_fin_meta
Create Date: 2026-09-27 16:48:57.578539
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "5e7e6c99f50d"
down_revision: Union[str, Sequence[str], None] = "0003_fin_meta"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "benchmark_prices",
        sa.Column("benchmark", sa.String(length=50), nullable=False),
        sa.Column("trade_date", sa.Date(), nullable=False),
        sa.Column(
            "open_price",
            sa.Numeric(precision=18, scale=6),
            nullable=True,
        ),
        sa.Column(
            "high_price",
            sa.Numeric(precision=18, scale=6),
            nullable=True,
        ),
        sa.Column(
            "low_price",
            sa.Numeric(precision=18, scale=6),
            nullable=True,
        ),
        sa.Column(
            "close_price",
            sa.Numeric(precision=18, scale=6),
            nullable=True,
        ),
        sa.Column("source", sa.String(length=50), nullable=False),
        sa.Column("source_reference", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("benchmark", "trade_date"),
    )


def downgrade() -> None:
    op.drop_table("benchmark_prices")