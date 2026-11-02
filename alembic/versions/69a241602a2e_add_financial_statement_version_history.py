
"""add financial statement version history

Revision ID: 69a241602a2e
Revises: 7e39dc59c8ed
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "69a241602a2e"
down_revision: Union[str, Sequence[str], None] = "7e39dc59c8ed"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "financial_statement_versions",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("raw_filing_id", sa.BigInteger(), nullable=False),
        sa.Column("company_id", sa.BigInteger(), nullable=False),
        sa.Column("period_type", sa.String(20), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("filing_date", sa.Date(), nullable=True),
        sa.Column("revenue", sa.Numeric(24, 4), nullable=True),
        sa.Column("ebitda", sa.Numeric(24, 4), nullable=True),
        sa.Column("ebit", sa.Numeric(24, 4), nullable=True),
        sa.Column("profit_before_tax", sa.Numeric(24, 4), nullable=True),
        sa.Column("net_income", sa.Numeric(24, 4), nullable=True),
        sa.Column("eps", sa.Numeric(18, 6), nullable=True),
        sa.Column("total_assets", sa.Numeric(24, 4), nullable=True),
        sa.Column("total_equity", sa.Numeric(24, 4), nullable=True),
        sa.Column("total_debt", sa.Numeric(24, 4), nullable=True),
        sa.Column("cash_and_equivalents", sa.Numeric(24, 4), nullable=True),
        sa.Column("operating_cash_flow", sa.Numeric(24, 4), nullable=True),
        sa.Column("capital_expenditure", sa.Numeric(24, 4), nullable=True),
        sa.Column("free_cash_flow", sa.Numeric(24, 4), nullable=True),
        sa.Column("source", sa.String(50), nullable=False),
        sa.Column("source_reference", sa.Text(), nullable=True),
        sa.Column("statement_scope", sa.String(20), nullable=False),
        sa.Column("submission_type", sa.String(20), nullable=False),
        sa.Column("audit_status", sa.String(20), nullable=True),
        sa.Column("reporting_standard", sa.String(30), nullable=True),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column(
            "reported_values",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
        ),
        sa.ForeignKeyConstraint(
            ["raw_filing_id"],
            ["financial_raw_filings.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "raw_filing_id",
            "period_type",
            "period_end",
            "statement_scope",
            "submission_type",
            name="uq_financial_statement_version_identity",
        ),
    )

    op.create_index(
        "ix_financial_statement_versions_company_period",
        "financial_statement_versions",
        ["company_id", "period_end"],
    )

    op.create_table(
        "financial_statement_version_sources",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("version_id", sa.BigInteger(), nullable=False),
        sa.Column("source_raw_filing_id", sa.BigInteger(), nullable=False),
        sa.Column("component", sa.String(20), nullable=False),
        sa.Column("source_role", sa.String(30), nullable=False),
        sa.Column("derivation_method", sa.String(30), nullable=False),
        sa.ForeignKeyConstraint(
            ["source_raw_filing_id"],
            ["financial_raw_filings.id"],
        ),
        sa.ForeignKeyConstraint(
            ["version_id"],
            ["financial_statement_versions.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "version_id",
            "source_raw_filing_id",
            "component",
            "source_role",
            name="uq_financial_statement_version_source",
        ),
    )

    op.create_index(
        "ix_financial_statement_version_sources_raw_filing",
        "financial_statement_version_sources",
        ["source_raw_filing_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_financial_statement_version_sources_raw_filing",
        table_name="financial_statement_version_sources",
    )
    op.drop_table("financial_statement_version_sources")

    op.drop_index(
        "ix_financial_statement_versions_company_period",
        table_name="financial_statement_versions",
    )
    op.drop_table("financial_statement_versions")
