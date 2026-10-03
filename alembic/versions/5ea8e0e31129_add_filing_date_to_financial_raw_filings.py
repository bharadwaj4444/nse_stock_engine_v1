"""add filing date to financial raw filings

Revision ID: 5ea8e0e31129
Revises: add_financial_raw_filings
Create Date: 2026-10-03 11:33:54.617790

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = '5ea8e0e31129'
down_revision: Union[str, Sequence[str], None] = 'add_financial_raw_filings'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.add_column(
        "financial_raw_filings",
        sa.Column(
            "filing_date",
            sa.Date(),
            nullable=True,
        ),
    )

def downgrade() -> None:
    op.drop_column(
        "financial_raw_filings",
        "filing_date",
    )
