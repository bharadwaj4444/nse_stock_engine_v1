"""add ttm latest filing date

Revision ID: 2c275747d292
Revises: 5ea8e0e31129
Create Date: 2026-10-03 15:29:11.807370

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = '2c275747d292'
down_revision: Union[str, Sequence[str], None] = '5ea8e0e31129'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.add_column(
        "ttm_financials",
        sa.Column("latest_filing_date", sa.Date(), nullable=True),
    )

def downgrade() -> None:
    op.drop_column("ttm_financials", "latest_filing_date")
