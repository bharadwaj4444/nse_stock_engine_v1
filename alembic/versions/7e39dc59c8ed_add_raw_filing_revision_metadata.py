
"""add raw filing revision metadata

Revision ID: 7e39dc59c8ed
Revises: b3f9a2c7d4e1
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "7e39dc59c8ed"
down_revision: Union[str, Sequence[str], None] = "b3f9a2c7d4e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "financial_raw_filings",
        sa.Column("broadcast_datetime", sa.DateTime(timezone=True), nullable=True),
    )

    op.add_column(
        "financial_raw_filings",
        sa.Column("revised_datetime", sa.DateTime(timezone=True), nullable=True),
    )

    op.add_column(
        "financial_raw_filings",
        sa.Column("revision_remarks", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("financial_raw_filings", "revision_remarks")
    op.drop_column("financial_raw_filings", "revised_datetime")
    op.drop_column("financial_raw_filings", "broadcast_datetime")
