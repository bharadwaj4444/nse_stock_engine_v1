from alembic import op
import sqlalchemy as sa

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        "companies",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("nse_symbol", sa.String(50), nullable=False, unique=True),
        sa.Column("isin", sa.String(20)),
        sa.Column("company_name", sa.Text(), nullable=False),
        sa.Column("series", sa.String(20)),
        sa.Column("listing_date", sa.Date()),
        sa.Column("status", sa.String(30)),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("source_updated_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_companies_active", "companies", ["is_active"])

    op.create_table(
        "daily_prices",
        sa.Column("company_id", sa.BigInteger(), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("trade_date", sa.Date(), nullable=False),
        sa.Column("open_price", sa.Numeric(18, 6)),
        sa.Column("high_price", sa.Numeric(18, 6)),
        sa.Column("low_price", sa.Numeric(18, 6)),
        sa.Column("close_price", sa.Numeric(18, 6)),
        sa.Column("prev_close", sa.Numeric(18, 6)),
        sa.Column("volume", sa.BigInteger()),
        sa.Column("traded_value", sa.Numeric(24, 4)),
        sa.Column("trades_count", sa.BigInteger()),
        sa.Column("delivery_qty", sa.BigInteger()),
        sa.Column("delivery_pct", sa.Numeric(10, 4)),
        sa.Column("vwap", sa.Numeric(18, 6)),
        sa.Column("source_file", sa.Text()),
        sa.PrimaryKeyConstraint("company_id", "trade_date"),
    )
    op.create_index("ix_daily_prices_date", "daily_prices", ["trade_date"])
    op.create_index("ix_daily_prices_company_date", "daily_prices", ["company_id", "trade_date"])

    op.create_table(
        "technical_indicators",
        sa.Column("company_id", sa.BigInteger(), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("trade_date", sa.Date(), nullable=False),
        sa.Column("sma20", sa.Numeric(18, 6)),
        sa.Column("sma50", sa.Numeric(18, 6)),
        sa.Column("sma100", sa.Numeric(18, 6)),
        sa.Column("sma200", sa.Numeric(18, 6)),
        sa.Column("ema20", sa.Numeric(18, 6)),
        sa.Column("ema50", sa.Numeric(18, 6)),
        sa.Column("rsi14", sa.Numeric(12, 6)),
        sa.Column("macd", sa.Numeric(18, 6)),
        sa.Column("macd_signal", sa.Numeric(18, 6)),
        sa.Column("macd_histogram", sa.Numeric(18, 6)),
        sa.Column("atr14", sa.Numeric(18, 6)),
        sa.Column("bb_upper", sa.Numeric(18, 6)),
        sa.Column("bb_middle", sa.Numeric(18, 6)),
        sa.Column("bb_lower", sa.Numeric(18, 6)),
        sa.Column("adx14", sa.Numeric(12, 6)),
        sa.Column("volatility20", sa.Numeric(12, 6)),
        sa.Column("volatility60", sa.Numeric(12, 6)),
        sa.Column("return_1d", sa.Numeric(12, 6)),
        sa.Column("return_5d", sa.Numeric(12, 6)),
        sa.Column("return_20d", sa.Numeric(12, 6)),
        sa.Column("return_60d", sa.Numeric(12, 6)),
        sa.Column("return_120d", sa.Numeric(12, 6)),
        sa.Column("return_252d", sa.Numeric(12, 6)),
        sa.Column("relative_volume20", sa.Numeric(12, 6)),
        sa.Column("nifty_relative_20d", sa.Numeric(12, 6)),
        sa.Column("nifty_relative_60d", sa.Numeric(12, 6)),
        sa.PrimaryKeyConstraint("company_id", "trade_date"),
    )
    op.create_index("ix_indicators_date", "technical_indicators", ["trade_date"])

    op.create_table(
        "ingestion_runs",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("run_type", sa.String(50), nullable=False),
        sa.Column("trade_date", sa.Date()),
        sa.Column("source", sa.String(50), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("records_seen", sa.Integer(), server_default="0"),
        sa.Column("records_written", sa.Integer(), server_default="0"),
        sa.Column("error_message", sa.Text()),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_ingestion_runs_date", "ingestion_runs", ["trade_date"])

def downgrade():
    op.drop_table("ingestion_runs")
    op.drop_table("technical_indicators")
    op.drop_table("daily_prices")
    op.drop_table("companies")
