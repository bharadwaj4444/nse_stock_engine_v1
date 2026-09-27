from alembic import op
import sqlalchemy as sa

revision = "0003_fin_meta"
down_revision = "0002_financials"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "financial_statements",
        sa.Column("statement_scope", sa.String(20), nullable=False, server_default="UNKNOWN"),
    )

    op.add_column(
        "financial_statements",
        sa.Column("submission_type", sa.String(20), nullable=False, server_default="ORIGINAL"),
    )

    op.add_column(
        "financial_statements",
        sa.Column("audit_status", sa.String(20)),
    )

    op.add_column(
        "financial_statements",
        sa.Column("reporting_standard", sa.String(30)),
    )

    op.add_column(
        "financial_statements",
        sa.Column("source_url", sa.Text()),
    )

    op.drop_constraint(
        "uq_financial_statement_period_source",
        "financial_statements",
        type_="unique",
    )

    op.create_unique_constraint(
        "uq_financial_statement_identity",
        "financial_statements",
        [
            "company_id",
            "period_type",
            "period_end",
            "statement_scope",
            "submission_type",
            "source",
        ],
    )


def downgrade():
    op.drop_constraint(
        "uq_financial_statement_identity",
        "financial_statements",
        type_="unique",
    )

    op.create_unique_constraint(
        "uq_financial_statement_period_source",
        "financial_statements",
        [
            "company_id",
            "period_type",
            "period_end",
            "source",
        ],
    )

    op.drop_column("financial_statements", "source_url")
    op.drop_column("financial_statements", "reporting_standard")
    op.drop_column("financial_statements", "audit_status")
    op.drop_column("financial_statements", "submission_type")
    op.drop_column("financial_statements", "statement_scope")