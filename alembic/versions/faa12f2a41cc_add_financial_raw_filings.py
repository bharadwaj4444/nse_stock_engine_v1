"""add financial raw filings

Revision ID: add_financial_raw_filings
Revises: add_share_capital
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "add_financial_raw_filings"
down_revision: Union[str, Sequence[str], None] = "add_share_capital"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "financial_raw_filings",

        sa.Column(
            "id",
            sa.BigInteger(),
            primary_key=True,
            autoincrement=True,
        ),

        sa.Column(
            "company_id",
            sa.BigInteger(),
            sa.ForeignKey("companies.id"),
            nullable=False,
        ),

        sa.Column(
            "symbol",
            sa.String(50),
            nullable=False,
        ),

        sa.Column(
            "period_end",
            sa.Date(),
            nullable=False,
        ),

        sa.Column(
            "statement_scope",
            sa.String(50),
            nullable=False,
        ),

        sa.Column(
            "submission_type",
            sa.String(50),
        ),

        sa.Column(
            "audit_status",
            sa.String(50),
        ),

        sa.Column(
            "source_reference",
            sa.String(100),
        ),

        sa.Column(
            "xbrl_url",
            sa.Text(),
        ),

        sa.Column(
            "raw_relative_path",
            sa.Text(),
            nullable=False,
        ),

        sa.Column(
            "sha256",
            sa.String(64),
            nullable=False,
        ),

        sa.Column(
            "file_size",
            sa.BigInteger(),
            nullable=False,
        ),

        sa.Column(
            "downloaded_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),

        sa.Column(
            "processed_at",
            sa.DateTime(timezone=True),
        ),

        sa.Column(
            "processing_status",
            sa.String(30),
            server_default="PENDING",
            nullable=False,
        ),

        sa.Column(
            "processing_error",
            sa.Text(),
        ),

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

        sa.UniqueConstraint(
            "company_id",
            "source_reference",
            "sha256",
            name="uq_financial_raw_filing_identity",
        ),
    )

    op.create_index(
        "ix_financial_raw_filings_company_id",
        "financial_raw_filings",
        ["company_id"],
    )

    op.create_index(
        "ix_financial_raw_filings_symbol",
        "financial_raw_filings",
        ["symbol"],
    )

    op.create_index(
        "ix_financial_raw_filings_period_end",
        "financial_raw_filings",
        ["period_end"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_financial_raw_filings_period_end",
        table_name="financial_raw_filings",
    )

    op.drop_index(
        "ix_financial_raw_filings_symbol",
        table_name="financial_raw_filings",
    )

    op.drop_index(
        "ix_financial_raw_filings_company_id",
        table_name="financial_raw_filings",
    )

    op.drop_table("financial_raw_filings")