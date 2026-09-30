"""add market metrics

Revision ID: add_market_metrics
Revises: add_financial_ratios
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "add_market_metrics"
down_revision: Union[str, Sequence[str], None] = "add_financial_ratios"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "market_metrics",
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

        sa.Column("trade_date", sa.Date(), nullable=False),

        # Market data
        sa.Column("close_price", sa.Numeric(24, 6)),
        sa.Column("vwap", sa.Numeric(24, 6)),
        sa.Column("volume", sa.BigInteger()),

        # Share data
        sa.Column("shares_outstanding", sa.Numeric(24, 4)),
        sa.Column("share_data_date", sa.Date()),

        # Derived market values
        sa.Column("market_cap", sa.Numeric(30, 4)),

        # Provenance
        sa.Column("price_source", sa.String(50)),
        sa.Column("share_source", sa.String(50)),
        sa.Column("calculation_method", sa.String(100)),

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
            "trade_date",
            name="uq_market_metrics_identity",
        ),
    )

    op.create_index(
        "ix_market_metrics_company_date",
        "market_metrics",
        ["company_id", "trade_date"],
    )

    op.create_index(
        "ix_market_metrics_trade_date",
        "market_metrics",
        ["trade_date"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_market_metrics_trade_date",
        table_name="market_metrics",
    )

    op.drop_index(
        "ix_market_metrics_company_date",
        table_name="market_metrics",
    )

    op.drop_table("market_metrics")