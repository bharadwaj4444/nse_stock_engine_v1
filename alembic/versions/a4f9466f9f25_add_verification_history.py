"""add verification history

Revision ID: a4f9466f9f25
Revises: 2588cd0f8574
"""

from alembic import op
import sqlalchemy as sa


revision = "a4f9466f9f25"
down_revision = "2588cd0f8574"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "verification_runs",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("trade_date", sa.Date(), nullable=False),
        sa.Column("trigger", sa.String(length=20), nullable=False),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "completed_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column("failure_count", sa.Integer(), nullable=False),
        sa.Column("warning_count", sa.Integer(), nullable=False),
        sa.Column("check_count", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "ix_verification_runs_trade_date_started_at",
        "verification_runs",
        ["trade_date", "started_at"],
    )

    op.create_table(
        "verification_results",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("run_id", sa.BigInteger(), nullable=False),
        sa.Column("check_name", sa.String(length=150), nullable=False),
        sa.Column("status", sa.String(length=10), nullable=False),
        sa.Column("expected", sa.Integer(), nullable=True),
        sa.Column("actual", sa.Integer(), nullable=True),
        sa.Column("details", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["verification_runs.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "run_id",
            "check_name",
            name="uq_verification_results_run_check",
        ),
    )

    op.create_index(
        "ix_verification_results_run_id",
        "verification_results",
        ["run_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_verification_results_run_id",
        table_name="verification_results",
    )
    op.drop_table("verification_results")

    op.drop_index(
        "ix_verification_runs_trade_date_started_at",
        table_name="verification_runs",
    )
    op.drop_table("verification_runs")