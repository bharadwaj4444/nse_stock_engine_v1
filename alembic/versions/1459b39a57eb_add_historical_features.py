"""add historical features

Revision ID: 1459b39a57eb
Revises: 7c4a1e9d8b21
Create Date: 2026-10-03 19:21:35.252896

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = '1459b39a57eb'
down_revision: Union[str, Sequence[str], None] = '7c4a1e9d8b21'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.create_table(
        "historical_features",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),

        sa.Column("company_id", sa.BigInteger(), nullable=False),
        sa.Column("trade_date", sa.Date(), nullable=False),

        # Market
        sa.Column("close_price", sa.Numeric(), nullable=True),
        sa.Column("volume", sa.Numeric(), nullable=True),
        sa.Column("market_cap", sa.Numeric(), nullable=True),

        # Momentum / trend
        sa.Column("return_5d", sa.Numeric(), nullable=True),
        sa.Column("return_20d", sa.Numeric(), nullable=True),
        sa.Column("return_60d", sa.Numeric(), nullable=True),
        sa.Column("return_120d", sa.Numeric(), nullable=True),
        sa.Column("return_252d", sa.Numeric(), nullable=True),

        sa.Column("sma20", sa.Numeric(), nullable=True),
        sa.Column("sma50", sa.Numeric(), nullable=True),
        sa.Column("sma200", sa.Numeric(), nullable=True),
        sa.Column("ema20", sa.Numeric(), nullable=True),
        sa.Column("ema50", sa.Numeric(), nullable=True),

        # Technical
        sa.Column("rsi14", sa.Numeric(), nullable=True),
        sa.Column("macd", sa.Numeric(), nullable=True),
        sa.Column("macd_signal", sa.Numeric(), nullable=True),
        sa.Column("macd_histogram", sa.Numeric(), nullable=True),
        sa.Column("atr14", sa.Numeric(), nullable=True),
        sa.Column("adx14", sa.Numeric(), nullable=True),
        sa.Column("volatility20", sa.Numeric(), nullable=True),
        sa.Column("volatility60", sa.Numeric(), nullable=True),
        sa.Column("relative_volume20", sa.Numeric(), nullable=True),

        # Relative strength
        sa.Column("nifty_relative_20d", sa.Numeric(), nullable=True),
        sa.Column("nifty_relative_60d", sa.Numeric(), nullable=True),

        # Fundamental provenance
        sa.Column("ttm_period_end", sa.Date(), nullable=True),
        sa.Column("ttm_filing_date", sa.Date(), nullable=True),

        # Fundamental quality
        sa.Column("ebitda_margin", sa.Numeric(), nullable=True),
        sa.Column("ebit_margin", sa.Numeric(), nullable=True),
        sa.Column("net_profit_margin", sa.Numeric(), nullable=True),
        sa.Column("roe", sa.Numeric(), nullable=True),
        sa.Column("roa", sa.Numeric(), nullable=True),

        sa.Column("debt_to_equity", sa.Numeric(), nullable=True),
        sa.Column("debt_to_ebitda", sa.Numeric(), nullable=True),
        sa.Column("net_debt_to_ebitda", sa.Numeric(), nullable=True),
        sa.Column("asset_turnover", sa.Numeric(), nullable=True),
        sa.Column("eps_ttm", sa.Numeric(), nullable=True),

        # Valuation
        sa.Column("pe_ratio", sa.Numeric(), nullable=True),
        sa.Column("price_to_sales", sa.Numeric(), nullable=True),
        sa.Column("price_to_fcf", sa.Numeric(), nullable=True),
        sa.Column("ev_to_ebitda", sa.Numeric(), nullable=True),
        sa.Column("ev_to_sales", sa.Numeric(), nullable=True),
        sa.Column("earnings_yield", sa.Numeric(), nullable=True),
        sa.Column("fcf_yield", sa.Numeric(), nullable=True),

        # Provenance
        sa.Column("statement_scope", sa.String(), nullable=False),
        sa.Column("calculation_method", sa.String(), nullable=True),

        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),

        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "company_id",
            "trade_date",
            "statement_scope",
            name="uq_historical_features_company_date_scope",
        ),
    )

    op.create_index(
        "ix_historical_features_trade_date",
        "historical_features",
        ["trade_date"],
    )

    op.create_index(
        "ix_historical_features_company_trade_date",
        "historical_features",
        ["company_id", "trade_date"],
    )

    op.create_index(
        "ix_historical_features_ttm_filing_date",
        "historical_features",
        ["ttm_filing_date"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_historical_features_ttm_filing_date",
        table_name="historical_features",
    )
    op.drop_index(
        "ix_historical_features_company_trade_date",
        table_name="historical_features",
    )
    op.drop_index(
        "ix_historical_features_trade_date",
        table_name="historical_features",
    )
    op.drop_table("historical_features")
