from alembic import op
import sqlalchemy as sa

revision = "0002_financials"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "financial_statements",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "company_id",
            sa.BigInteger(),
            sa.ForeignKey("companies.id"),
            nullable=False,
        ),

        # FY / quarter / TTM
        sa.Column("period_type", sa.String(20), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("filing_date", sa.Date()),

        # Income statement
        sa.Column("revenue", sa.Numeric(24, 4)),
        sa.Column("ebitda", sa.Numeric(24, 4)),
        sa.Column("ebit", sa.Numeric(24, 4)),
        sa.Column("profit_before_tax", sa.Numeric(24, 4)),
        sa.Column("net_income", sa.Numeric(24, 4)),
        sa.Column("eps", sa.Numeric(18, 6)),

        # Balance sheet
        sa.Column("total_assets", sa.Numeric(24, 4)),
        sa.Column("total_equity", sa.Numeric(24, 4)),
        sa.Column("total_debt", sa.Numeric(24, 4)),
        sa.Column("cash_and_equivalents", sa.Numeric(24, 4)),

        # Cash flow
        sa.Column("operating_cash_flow", sa.Numeric(24, 4)),
        sa.Column("capital_expenditure", sa.Numeric(24, 4)),
        sa.Column("free_cash_flow", sa.Numeric(24, 4)),

        # Source tracking
        sa.Column("source", sa.String(50), nullable=False),
        sa.Column("source_reference", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),

        sa.UniqueConstraint(
            "company_id",
            "period_type",
            "period_end",
            "source",
            name="uq_financial_statement_period_source",
        ),
    )

    op.create_index(
        "ix_financial_statements_company_period",
        "financial_statements",
        ["company_id", "period_end"],
    )

    op.create_index(
        "ix_financial_statements_period_end",
        "financial_statements",
        ["period_end"],
    )


def downgrade():
    op.drop_table("financial_statements")