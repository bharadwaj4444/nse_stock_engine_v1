"""add closed loop state

Revision ID: b3f9a2c7d4e1
Revises: a4f9466f9f25
Create Date: 2026-11-01 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b3f9a2c7d4e1"
down_revision: Union[str, Sequence[str], None] = "a4f9466f9f25"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "hold_decisions",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("company_id", sa.BigInteger(), nullable=False),
        sa.Column("trade_date", sa.Date(), nullable=False),
        sa.Column("action", sa.String(length=20), nullable=False),
        sa.Column("score", sa.Numeric(10, 6), nullable=True),
        sa.Column("red_green", sa.String(length=20), nullable=False),
        sa.Column("action_reason", sa.String(length=50), nullable=False),
        sa.Column("hold_until", sa.Date(), nullable=True),
        sa.Column("sell_target_price", sa.Numeric(18, 6), nullable=True),
        sa.Column("sell_target_date", sa.Date(), nullable=True),
        sa.Column("expected_return", sa.Numeric(18, 6), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "ix_hold_decisions_trade_date",
        "hold_decisions",
        ["trade_date"],
    )

    op.create_index(
        "ix_hold_decisions_company_trade_date",
        "hold_decisions",
        ["company_id", "trade_date"],
    )

    op.create_table(
        "outcomes",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("company_id", sa.BigInteger(), nullable=False),
        sa.Column("trade_date", sa.Date(), nullable=False),
        sa.Column("expected_return", sa.Numeric(18, 6), nullable=True),
        sa.Column("actual_return", sa.Numeric(18, 6), nullable=True),
        sa.Column("deviation", sa.Numeric(18, 6), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "ix_outcomes_trade_date",
        "outcomes",
        ["trade_date"],
    )

    op.create_index(
        "ix_outcomes_company_trade_date",
        "outcomes",
        ["company_id", "trade_date"],
    )

    op.create_table(
        "news_signals",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("company_id", sa.BigInteger(), nullable=False),
        sa.Column("trade_date", sa.Date(), nullable=False),
        sa.Column("source", sa.String(length=50), nullable=False),
        sa.Column("sentiment", sa.String(length=20), nullable=False),
        sa.Column("score_adjustment", sa.Numeric(10, 6), nullable=True),
        sa.Column("significance", sa.String(length=20), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "ix_news_signals_trade_date",
        "news_signals",
        ["trade_date"],
    )

    op.create_table(
        "overrides",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("company_id", sa.BigInteger(), nullable=False),
        sa.Column("trade_date", sa.Date(), nullable=False),
        sa.Column("source", sa.String(length=50), nullable=False),
        sa.Column("sentiment", sa.String(length=20), nullable=False),
        sa.Column("original_score", sa.Numeric(10, 6), nullable=True),
        sa.Column("adjusted_score", sa.Numeric(10, 6), nullable=True),
        sa.Column("adjustment", sa.Numeric(10, 6), nullable=True),
        sa.Column("significance_status", sa.String(length=20), nullable=False),
        sa.Column("applied", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "ix_overrides_trade_date",
        "overrides",
        ["trade_date"],
    )

    op.create_unique_constraint(
        "uq_hold_decisions_company_trade_date",
        "hold_decisions",
        ["company_id", "trade_date"],
    )

    op.create_unique_constraint(
        "uq_outcomes_company_trade_date",
        "outcomes",
        ["company_id", "trade_date"],
    )

    op.create_unique_constraint(
        "uq_news_signals_company_date_source",
        "news_signals",
        ["company_id", "trade_date", "source"],
    )

    op.create_unique_constraint(
        "uq_overrides_company_date_source",
        "overrides",
        ["company_id", "trade_date", "source"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_overrides_company_date_source",
        "overrides",
        type_="unique",
    )
    op.drop_index("ix_overrides_trade_date", table_name="overrides")
    op.drop_table("overrides")

    op.drop_constraint(
        "uq_news_signals_company_date_source",
        "news_signals",
        type_="unique",
    )
    op.drop_index("ix_news_signals_trade_date", table_name="news_signals")
    op.drop_table("news_signals")

    op.drop_constraint(
        "uq_outcomes_company_trade_date",
        "outcomes",
        type_="unique",
    )
    op.drop_index("ix_outcomes_company_trade_date", table_name="outcomes")
    op.drop_index("ix_outcomes_trade_date", table_name="outcomes")
    op.drop_table("outcomes")

    op.drop_constraint(
        "uq_hold_decisions_company_trade_date",
        "hold_decisions",
        type_="unique",
    )
    op.drop_index("ix_hold_decisions_company_trade_date", table_name="hold_decisions")
    op.drop_index("ix_hold_decisions_trade_date", table_name="hold_decisions")
    op.drop_table("hold_decisions")
