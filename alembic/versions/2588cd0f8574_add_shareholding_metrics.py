"""add shareholding metrics

Revision ID: 2588cd0f8574
Revises: 1d350eb1755d
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "2588cd0f8574"
down_revision: Union[str, Sequence[str], None] = "1d350eb1755d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "shareholding_metrics",

        sa.Column(
            "id",
            sa.BigInteger(),
            autoincrement=True,
            nullable=False,
        ),

        sa.Column(
            "company_id",
            sa.BigInteger(),
            nullable=False,
        ),

        sa.Column(
            "effective_date",
            sa.Date(),
            nullable=False,
        ),

        sa.Column(
            "total_shares",
            sa.BigInteger(),
            nullable=False,
        ),

        sa.Column("promoter_pct", sa.Numeric(12, 6)),
        sa.Column("public_pct", sa.Numeric(12, 6)),
        sa.Column("non_promoter_non_public_pct", sa.Numeric(12, 6)),
        sa.Column("government_pct", sa.Numeric(12, 6)),
        sa.Column("domestic_institutions_pct", sa.Numeric(12, 6)),
        sa.Column("foreign_institutions_pct", sa.Numeric(12, 6)),
        sa.Column("non_institutions_pct", sa.Numeric(12, 6)),
        sa.Column("mutual_funds_pct", sa.Numeric(12, 6)),
        sa.Column("venture_capital_funds_pct", sa.Numeric(12, 6)),
        sa.Column("alternative_investment_funds_pct", sa.Numeric(12, 6)),
        sa.Column("banks_pct", sa.Numeric(12, 6)),
        sa.Column("insurance_companies_pct", sa.Numeric(12, 6)),
        sa.Column("provident_pension_funds_pct", sa.Numeric(12, 6)),
        sa.Column("fdi_pct", sa.Numeric(12, 6)),
        sa.Column("foreign_vc_investors_pct", sa.Numeric(12, 6)),
        sa.Column("foreign_sovereign_wealth_funds_pct", sa.Numeric(12, 6)),
        sa.Column("fpi_category_i_pct", sa.Numeric(12, 6)),
        sa.Column("fpi_category_ii_pct", sa.Numeric(12, 6)),
        sa.Column("overseas_depositories_pct", sa.Numeric(12, 6)),
        sa.Column("resident_individuals_upto_2l_pct", sa.Numeric(12, 6)),
        sa.Column("resident_individuals_above_2l_pct", sa.Numeric(12, 6)),
        sa.Column("nris_pct", sa.Numeric(12, 6)),
        sa.Column("foreign_nationals_pct", sa.Numeric(12, 6)),
        sa.Column("foreign_companies_pct", sa.Numeric(12, 6)),
        sa.Column("bodies_corporate_pct", sa.Numeric(12, 6)),
        sa.Column("other_non_institutions_pct", sa.Numeric(12, 6)),

        sa.Column(
            "source",
            sa.String(50),
            nullable=False,
            server_default="NSE",
        ),

        sa.Column(
            "calculation_method",
            sa.String(100),
            nullable=False,
            server_default="NSE_SHAREHOLDING_PERCENTAGE",
        ),

        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),

        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),

        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            ondelete="CASCADE",
            name="shareholding_metrics_company_id_fkey",
        ),

        sa.PrimaryKeyConstraint("id"),

        sa.UniqueConstraint(
            "company_id",
            "effective_date",
            name="uq_shareholding_metrics_identity",
        ),
    )

    op.create_index(
        "ix_shareholding_metrics_company_date",
        "shareholding_metrics",
        ["company_id", "effective_date"],
    )

    op.create_index(
        "ix_shareholding_metrics_date",
        "shareholding_metrics",
        ["effective_date"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_shareholding_metrics_date",
        table_name="shareholding_metrics",
    )

    op.drop_index(
        "ix_shareholding_metrics_company_date",
        table_name="shareholding_metrics",
    )

    op.drop_table("shareholding_metrics")