"""add historical feature scores

Revision ID: d12089cea0d5
Revises: 1459b39a57eb
Create Date: 2026-10-03 19:43:24.630457

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = 'd12089cea0d5'
down_revision: Union[str, Sequence[str], None] = '1459b39a57eb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.create_table(
        "historical_feature_scores",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("company_id", sa.BigInteger(), nullable=False),
        sa.Column("trade_date", sa.Date(), nullable=False),
        sa.Column("statement_scope", sa.String(length=32), nullable=False),

        sa.Column("return_5d_score", sa.Numeric(10, 6)),
        sa.Column("return_20d_score", sa.Numeric(10, 6)),
        sa.Column("return_60d_score", sa.Numeric(10, 6)),
        sa.Column("return_120d_score", sa.Numeric(10, 6)),

        sa.Column("roe_score", sa.Numeric(10, 6)),
        sa.Column("roa_score", sa.Numeric(10, 6)),
        sa.Column("ebitda_margin_score", sa.Numeric(10, 6)),
        sa.Column("ebit_margin_score", sa.Numeric(10, 6)),
        sa.Column("net_profit_margin_score", sa.Numeric(10, 6)),

        sa.Column("debt_to_equity_score", sa.Numeric(10, 6)),
        sa.Column("debt_to_ebitda_score", sa.Numeric(10, 6)),
        sa.Column("net_debt_to_ebitda_score", sa.Numeric(10, 6)),

        sa.Column("pe_score", sa.Numeric(10, 6)),
        sa.Column("price_to_sales_score", sa.Numeric(10, 6)),
        sa.Column("ev_to_ebitda_score", sa.Numeric(10, 6)),
        sa.Column("earnings_yield_score", sa.Numeric(10, 6)),

        sa.Column(
            "calculation_method",
            sa.String(length=64),
            nullable=False,
        ),

        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),

        sa.UniqueConstraint(
            "company_id",
            "trade_date",
            "statement_scope",
            name="uq_historical_feature_scores_identity",
        ),
    )

    op.create_index(
        "ix_historical_feature_scores_trade_date",
        "historical_feature_scores",
        ["trade_date"],
    )

    op.create_index(
        "ix_historical_feature_scores_company_trade_date",
        "historical_feature_scores",
        ["company_id", "trade_date"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_historical_feature_scores_company_trade_date",
        table_name="historical_feature_scores",
    )
    op.drop_index(
        "ix_historical_feature_scores_trade_date",
        table_name="historical_feature_scores",
    )
    op.drop_table("historical_feature_scores")
