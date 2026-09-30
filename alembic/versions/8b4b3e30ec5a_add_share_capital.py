"""add share capital

Revision ID: add_share_capital
Revises: add_market_metrics
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "add_share_capital"
down_revision: Union[str, Sequence[str], None] = "add_market_metrics"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "share_capital",
        sa.Column(
            "id",
            sa.BigInteger(),
            primary_key=True,
            autoincrement=True,
        ),

        sa.Column(
            "company_id",
            sa.BigInteger(),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),

        # Date on which the share count applies.
        sa.Column("effective_date", sa.Date(), nullable=False),

        # Total equity shares outstanding.
        sa.Column(
            "shares_outstanding",
            sa.Numeric(24, 4),
            nullable=False,
        ),

        sa.Column(
            "share_type",
            sa.String(30),
            nullable=False,
            server_default="EQUITY",
        ),

        # Date on which NSE/company filing was submitted.
        sa.Column("filing_date", sa.Date()),

        sa.Column(
            "source",
            sa.String(50),
            nullable=False,
            server_default="NSE",
        ),

        sa.Column("source_url", sa.Text()),

        sa.Column(
            "calculation_method",
            sa.String(100),
            nullable=False,
            server_default="NSE_SHAREHOLDING_PATTERN",
        ),

        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),

        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),

        sa.UniqueConstraint(
            "company_id",
            "effective_date",
            "share_type",
            name="uq_share_capital_identity",
        ),
    )

    op.create_index(
        "ix_share_capital_company_date",
        "share_capital",
        ["company_id", "effective_date"],
    )

    op.create_index(
        "ix_share_capital_date",
        "share_capital",
        ["effective_date"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_share_capital_date",
        table_name="share_capital",
    )

    op.drop_index(
        "ix_share_capital_company_date",
        table_name="share_capital",
    )

    op.drop_table("share_capital")