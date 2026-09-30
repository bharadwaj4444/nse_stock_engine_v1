"""add ttm financials

Revision ID: 6d329b117f2a
Revises: 5e7e6c99f50d
Create Date: 2026-09-29

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "6d329b117f2a"
down_revision: Union[str, Sequence[str], None] = "5e7e6c99f50d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ttm_financials",

        sa.Column(
            "id",
            sa.BigInteger(),
            primary_key=True,
        ),

        sa.Column(
            "company_id",
            sa.BigInteger(),
            sa.ForeignKey("companies.id"),
            nullable=False,
        ),

        # TTM measurement date.
        # Usually the latest quarter-end for which TTM is calculated.
        sa.Column(
            "period_end",
            sa.Date(),
            nullable=False,
        ),

        # Consolidated / Standalone
        sa.Column(
            "statement_scope",
            sa.String(20),
            nullable=False,
        ),

        # -------------------------
        # TTM income statement
        # -------------------------

        sa.Column(
            "revenue_ttm",
            sa.Numeric(24, 4),
        ),

        sa.Column(
            "ebitda_ttm",
            sa.Numeric(24, 4),
        ),

        sa.Column(
            "ebit_ttm",
            sa.Numeric(24, 4),
        ),

        sa.Column(
            "profit_before_tax_ttm",
            sa.Numeric(24, 4),
        ),

        sa.Column(
            "net_income_ttm",
            sa.Numeric(24, 4),
        ),

        sa.Column(
            "eps_ttm",
            sa.Numeric(18, 6),
        ),

        # -------------------------
        # TTM cash flow
        # -------------------------

        sa.Column(
            "operating_cash_flow_ttm",
            sa.Numeric(24, 4),
        ),

        sa.Column(
            "capital_expenditure_ttm",
            sa.Numeric(24, 4),
        ),

        sa.Column(
            "free_cash_flow_ttm",
            sa.Numeric(24, 4),
        ),

        # -------------------------
        # Latest balance sheet
        # Point-in-time, NOT TTM
        # -------------------------

        sa.Column(
            "total_assets",
            sa.Numeric(24, 4),
        ),

        sa.Column(
            "total_equity",
            sa.Numeric(24, 4),
        ),

        sa.Column(
            "total_debt",
            sa.Numeric(24, 4),
        ),

        sa.Column(
            "cash_and_equivalents",
            sa.Numeric(24, 4),
        ),

        # -------------------------
        # Calculation provenance
        # -------------------------

        sa.Column(
            "calculation_method",
            sa.String(50),
            nullable=False,
        ),

        sa.Column(
            "source_periods",
            sa.Text(),
            nullable=False,
        ),

        sa.Column(
            "source",
            sa.String(50),
            nullable=False,
            server_default="DERIVED",
        ),

        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),

        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),

        sa.UniqueConstraint(
            "company_id",
            "period_end",
            "statement_scope",
            name="uq_ttm_financial_identity",
        ),
    )

    op.create_index(
        "ix_ttm_financials_company_period",
        "ttm_financials",
        ["company_id", "period_end"],
    )

    op.create_index(
        "ix_ttm_financials_period_end",
        "ttm_financials",
        ["period_end"],
    )

    op.create_index(
        "ix_ttm_financials_scope_period",
        "ttm_financials",
        ["statement_scope", "period_end"],
    )


def downgrade() -> None:
    op.drop_table("ttm_financials")