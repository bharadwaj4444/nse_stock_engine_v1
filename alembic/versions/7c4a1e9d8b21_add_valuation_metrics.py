"""add valuation metrics

Revision ID: 7c4a1e9d8b21
Revises: 2c275747d292
Create Date: 2026-10-03
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "7c4a1e9d8b21"
down_revision: Union[str, Sequence[str], None] = "2c275747d292"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "valuation_metrics",

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

        sa.Column(
            "valuation_date",
            sa.Date(),
            nullable=False,
        ),

        sa.Column(
            "statement_scope",
            sa.String(20),
            nullable=False,
        ),

        # Market value
        sa.Column(
            "market_cap",
            sa.Numeric(30, 4),
        ),

        sa.Column(
            "enterprise_value",
            sa.Numeric(30, 4),
        ),

        # Point-in-time TTM provenance
        sa.Column(
            "ttm_period_end",
            sa.Date(),
        ),

        sa.Column(
            "ttm_filing_date",
            sa.Date(),
        ),

        # Valuation multiples
        sa.Column(
            "pe_ratio",
            sa.Numeric(24, 6),
        ),

        sa.Column(
            "price_to_sales",
            sa.Numeric(24, 6),
        ),

        sa.Column(
            "price_to_fcf",
            sa.Numeric(24, 6),
        ),

        sa.Column(
            "ev_to_ebitda",
            sa.Numeric(24, 6),
        ),

        sa.Column(
            "ev_to_sales",
            sa.Numeric(24, 6),
        ),

        # Valuation yields
        sa.Column(
            "earnings_yield",
            sa.Numeric(24, 6),
        ),

        sa.Column(
            "fcf_yield",
            sa.Numeric(24, 6),
        ),

        # Provenance
        sa.Column(
            "calculation_method",
            sa.String(100),
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
            "valuation_date",
            "statement_scope",
            name="uq_valuation_metrics_identity",
        ),
    )

    op.create_index(
        "ix_valuation_metrics_company_date",
        "valuation_metrics",
        ["company_id", "valuation_date"],
    )

    op.create_index(
        "ix_valuation_metrics_valuation_date",
        "valuation_metrics",
        ["valuation_date"],
    )

    op.create_index(
        "ix_valuation_metrics_scope_date",
        "valuation_metrics",
        ["statement_scope", "valuation_date"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_valuation_metrics_scope_date",
        table_name="valuation_metrics",
    )

    op.drop_index(
        "ix_valuation_metrics_valuation_date",
        table_name="valuation_metrics",
    )

    op.drop_index(
        "ix_valuation_metrics_company_date",
        table_name="valuation_metrics",
    )

    op.drop_table("valuation_metrics")