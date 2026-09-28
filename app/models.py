from datetime import date, datetime
from decimal import Decimal
from sqlalchemy import BigInteger, Boolean, Date, DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

class Base(DeclarativeBase):
    pass

class Company(Base):
    __tablename__ = "companies"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    nse_symbol: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    isin: Mapped[str | None] = mapped_column(String(20))
    company_name: Mapped[str] = mapped_column(Text, nullable=False)
    series: Mapped[str | None] = mapped_column(String(20))
    listing_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str | None] = mapped_column(String(30))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    source_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

class DailyPrice(Base):
    __tablename__ = "daily_prices"
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), primary_key=True)
    trade_date: Mapped[date] = mapped_column(Date, primary_key=True)
    open_price: Mapped[Decimal | None] = mapped_column(Numeric(18,6))
    high_price: Mapped[Decimal | None] = mapped_column(Numeric(18,6))
    low_price: Mapped[Decimal | None] = mapped_column(Numeric(18,6))
    close_price: Mapped[Decimal | None] = mapped_column(Numeric(18,6))
    prev_close: Mapped[Decimal | None] = mapped_column(Numeric(18,6))
    volume: Mapped[int | None] = mapped_column(BigInteger)
    traded_value: Mapped[Decimal | None] = mapped_column(Numeric(24,4))
    trades_count: Mapped[int | None] = mapped_column(BigInteger)
    delivery_qty: Mapped[int | None] = mapped_column(BigInteger)
    delivery_pct: Mapped[Decimal | None] = mapped_column(Numeric(10,4))
    vwap: Mapped[Decimal | None] = mapped_column(Numeric(18,6))
    source_file: Mapped[str | None] = mapped_column(Text)

class TechnicalIndicator(Base):
    __tablename__ = "technical_indicators"
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), primary_key=True)
    trade_date: Mapped[date] = mapped_column(Date, primary_key=True)
    sma20: Mapped[Decimal | None] = mapped_column(Numeric(18,6))
    sma50: Mapped[Decimal | None] = mapped_column(Numeric(18,6))
    sma100: Mapped[Decimal | None] = mapped_column(Numeric(18,6))
    sma200: Mapped[Decimal | None] = mapped_column(Numeric(18,6))
    ema20: Mapped[Decimal | None] = mapped_column(Numeric(18,6))
    ema50: Mapped[Decimal | None] = mapped_column(Numeric(18,6))
    rsi14: Mapped[Decimal | None] = mapped_column(Numeric(12,6))
    macd: Mapped[Decimal | None] = mapped_column(Numeric(18,6))
    macd_signal: Mapped[Decimal | None] = mapped_column(Numeric(18,6))
    macd_histogram: Mapped[Decimal | None] = mapped_column(Numeric(18,6))
    atr14: Mapped[Decimal | None] = mapped_column(Numeric(18,6))
    bb_upper: Mapped[Decimal | None] = mapped_column(Numeric(18,6))
    bb_middle: Mapped[Decimal | None] = mapped_column(Numeric(18,6))
    bb_lower: Mapped[Decimal | None] = mapped_column(Numeric(18,6))
    adx14: Mapped[Decimal | None] = mapped_column(Numeric(12,6))
    volatility20: Mapped[Decimal | None] = mapped_column(Numeric(12,6))
    volatility60: Mapped[Decimal | None] = mapped_column(Numeric(12,6))
    return_1d: Mapped[Decimal | None] = mapped_column(Numeric(12,6))
    return_5d: Mapped[Decimal | None] = mapped_column(Numeric(12,6))
    return_20d: Mapped[Decimal | None] = mapped_column(Numeric(12,6))
    return_60d: Mapped[Decimal | None] = mapped_column(Numeric(12,6))
    return_120d: Mapped[Decimal | None] = mapped_column(Numeric(12,6))
    return_252d: Mapped[Decimal | None] = mapped_column(Numeric(12,6))
    relative_volume20: Mapped[Decimal | None] = mapped_column(Numeric(12,6))
    nifty_relative_20d: Mapped[Decimal | None] = mapped_column(Numeric(12,6))
    nifty_relative_60d: Mapped[Decimal | None] = mapped_column(Numeric(12,6))

class BenchmarkPrice(Base):
    __tablename__ = "benchmark_prices"

    benchmark: Mapped[str] = mapped_column(String(50), primary_key=True)
    trade_date: Mapped[date] = mapped_column(Date, primary_key=True)

    open_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    high_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    low_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    close_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))

    source: Mapped[str] = mapped_column(String(50), nullable=False)
    source_reference: Mapped[str | None] = mapped_column(Text)

class FinancialStatement(Base):
    __tablename__ = "financial_statements"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)

    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id"),
        nullable=False,
    )

    # FY / quarter / TTM
    period_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    period_end: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )

    filing_date: Mapped[date | None] = mapped_column(Date)

    # Income statement
    revenue: Mapped[Decimal | None] = mapped_column(
        Numeric(24, 4)
    )
    ebitda: Mapped[Decimal | None] = mapped_column(
        Numeric(24, 4)
    )
    ebit: Mapped[Decimal | None] = mapped_column(
        Numeric(24, 4)
    )
    profit_before_tax: Mapped[Decimal | None] = mapped_column(
        Numeric(24, 4)
    )
    net_income: Mapped[Decimal | None] = mapped_column(
        Numeric(24, 4)
    )
    eps: Mapped[Decimal | None] = mapped_column(
        Numeric(18, 6)
    )

    # Balance sheet
    total_assets: Mapped[Decimal | None] = mapped_column(
        Numeric(24, 4)
    )
    total_equity: Mapped[Decimal | None] = mapped_column(
        Numeric(24, 4)
    )
    total_debt: Mapped[Decimal | None] = mapped_column(
        Numeric(24, 4)
    )
    cash_and_equivalents: Mapped[Decimal | None] = mapped_column(
        Numeric(24, 4)
    )

    # Cash flow
    operating_cash_flow: Mapped[Decimal | None] = mapped_column(
        Numeric(24, 4)
    )
    capital_expenditure: Mapped[Decimal | None] = mapped_column(
        Numeric(24, 4)
    )
    free_cash_flow: Mapped[Decimal | None] = mapped_column(
        Numeric(24, 4)
    )

    # Source tracking
    source: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    source_reference: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )

    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )

    statement_scope: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="UNKNOWN",
    )

    submission_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="ORIGINAL",
    )

    audit_status: Mapped[str | None] = mapped_column(
        String(20)
    )

    reporting_standard: Mapped[str | None] = mapped_column(
        String(30)
    )

    source_url: Mapped[str | None] = mapped_column(
        Text
    )

class IngestionRun(Base):
    __tablename__ = "ingestion_runs"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    run_type: Mapped[str] = mapped_column(String(50), nullable=False)
    trade_date: Mapped[date | None] = mapped_column(Date)
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    records_seen: Mapped[int] = mapped_column(default=0)
    records_written: Mapped[int] = mapped_column(default=0)
    error_message: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
