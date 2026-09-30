"""add financial ratios

Revision ID: add_financial_ratios
Revises: 6d329b117f2a
Create Date: 2026-09-29
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "add_financial_ratios"
down_revision: Union[str, Sequence[str], None] = "6d329b117f2a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "financial_ratios",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),

        sa.Column(
            "company_id",
            sa.BigInteger(),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),

        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("statement_scope", sa.String(20), nullable=False),

        # Profitability
        sa.Column("ebitda_margin", sa.Numeric(18, 6)),
        sa.Column("ebit_margin", sa.Numeric(18, 6)),
        sa.Column("net_profit_margin", sa.Numeric(18, 6)),
        sa.Column("roe", sa.Numeric(18, 6)),
        sa.Column("roa", sa.Numeric(18, 6)),

        # Growth - YoY
        sa.Column("revenue_growth_yoy", sa.Numeric(18, 6)),
        sa.Column("ebitda_growth_yoy", sa.Numeric(18, 6)),
        sa.Column("ebit_growth_yoy", sa.Numeric(18, 6)),
        sa.Column("net_income_growth_yoy", sa.Numeric(18, 6)),
        sa.Column("eps_growth_yoy", sa.Numeric(18, 6)),

        # Leverage
        sa.Column("debt_to_equity", sa.Numeric(18, 6)),
        sa.Column("debt_to_ebitda", sa.Numeric(18, 6)),
        sa.Column("net_debt_to_ebitda", sa.Numeric(18, 6)),

        # Efficiency
        sa.Column("asset_turnover", sa.Numeric(18, 6)),

        # Per-share
        sa.Column("eps_ttm", sa.Numeric(18, 6)),

        # Cash-flow ratios - populated later
        sa.Column("operating_cash_flow_margin", sa.Numeric(18, 6)),
        sa.Column("free_cash_flow_margin", sa.Numeric(18, 6)),
        sa.Column("fcf_to_net_income", sa.Numeric(18, 6)),
        sa.Column("ocf_to_net_income", sa.Numeric(18, 6)),

        # Provenance
        sa.Column("calculation_method", sa.String(100), nullable=False),
        sa.Column("source_period", sa.Date(), nullable=False),
        sa.Column("prior_period", sa.Date()),
        sa.Column("source", sa.String(50), nullable=False, server_default="DERIVED"),

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
            "period_end",
            "statement_scope",
            name="uq_financial_ratio_identity",
        ),
    )

    op.create_index(
        "ix_financial_ratios_company_period",
        "financial_ratios",
        ["company_id", "period_end"],
    )

    op.create_index(
        "ix_financial_ratios_period",
        "financial_ratios",
        ["period_end"],
    )

    op.create_index(
        "ix_financial_ratios_scope_period",
        "financial_ratios",
        ["statement_scope", "period_end"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_financial_ratios_scope_period",
        table_name="financial_ratios",
    )

    op.drop_index(
        "ix_financial_ratios_period",
        table_name="financial_ratios",
    )

    op.drop_index(
        "ix_financial_ratios_company_period",
        table_name="financial_ratios",
    )

    op.drop_table("financial_ratios")