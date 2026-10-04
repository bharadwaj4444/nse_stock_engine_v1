"""add stock rankings

Revision ID: e9e24f0aa631
Revises: d12089cea0d5
Create Date: 2026-10-03 19:59:09.839417

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e9e24f0aa631"
down_revision: Union[str, Sequence[str], None] = "d12089cea0d5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "stock_rankings",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("company_id", sa.BigInteger(), nullable=False),
        sa.Column("trade_date", sa.Date(), nullable=False),
        sa.Column("statement_scope", sa.String(length=32), nullable=False),

        # Category scores
        sa.Column("momentum_score", sa.Numeric(10, 6), nullable=True),
        sa.Column("profitability_score", sa.Numeric(10, 6), nullable=True),
        sa.Column("leverage_score", sa.Numeric(10, 6), nullable=True),
        sa.Column("valuation_score", sa.Numeric(10, 6), nullable=True),

        # Overall score and cross-sectional rank
        sa.Column("overall_score", sa.Numeric(10, 6), nullable=True),
        sa.Column("overall_rank", sa.Integer(), nullable=True),
        sa.Column("overall_percentile", sa.Numeric(10, 6), nullable=True),

        # Coverage / eligibility diagnostics
        sa.Column("valid_feature_count", sa.Integer(), nullable=False),
        sa.Column("valid_category_count", sa.Integer(), nullable=False),

        # Versioned calculation definition
        sa.Column("calculation_method", sa.String(length=64), nullable=False),

        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),

        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
        ),
        sa.UniqueConstraint(
            "company_id",
            "trade_date",
            "statement_scope",
            name="uq_stock_rankings_company_date_scope",
        ),
    )

    op.create_index(
        "ix_stock_rankings_trade_date",
        "stock_rankings",
        ["trade_date"],
    )

    op.create_index(
        "ix_stock_rankings_company_trade_date",
        "stock_rankings",
        ["company_id", "trade_date"],
    )

    op.create_index(
        "ix_stock_rankings_overall_score",
        "stock_rankings",
        ["trade_date", "overall_score"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_stock_rankings_overall_score",
        table_name="stock_rankings",
    )

    op.drop_index(
        "ix_stock_rankings_company_trade_date",
        table_name="stock_rankings",
    )

    op.drop_index(
        "ix_stock_rankings_trade_date",
        table_name="stock_rankings",
    )

    op.drop_table("stock_rankings")