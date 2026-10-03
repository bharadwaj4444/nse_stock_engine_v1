from datetime import date, datetime
from decimal import Decimal
from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
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
    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "period_type",
            "period_end",
            "statement_scope",
            "submission_type",
            "source",
            name="uq_financial_statement_identity",
        ),
    )

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

class ShareCapital(Base):
    __tablename__ = "share_capital"

    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "effective_date",
            "share_type",
            name="uq_share_capital_identity",
        ),
        Index(
            "ix_share_capital_company_date",
            "company_id",
            "effective_date",
        ),
        Index(
            "ix_share_capital_date",
            "effective_date",
        ),
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )

    company_id: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
    )

    effective_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )

    shares_outstanding: Mapped[Decimal] = mapped_column(
        Numeric(24, 4),
        nullable=False,
    )

    share_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="EQUITY",
        server_default="EQUITY",
    )

    filing_date: Mapped[date | None] = mapped_column(Date)

    source: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="NSE",
        server_default="NSE",
    )

    source_url: Mapped[str | None] = mapped_column(Text)

    calculation_method: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        default="NSE_SHAREHOLDING_PATTERN",
        server_default="NSE_SHAREHOLDING_PATTERN",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class MarketMetric(Base):
    __tablename__ = "market_metrics"

    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "trade_date",
            name="uq_market_metrics_identity",
        ),
        Index(
            "ix_market_metrics_company_date",
            "company_id",
            "trade_date",
        ),
        Index(
            "ix_market_metrics_trade_date",
            "trade_date",
        ),
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )

    company_id: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
    )

    trade_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )

    close_price: Mapped[Decimal | None] = mapped_column(
        Numeric(24, 6)
    )

    vwap: Mapped[Decimal | None] = mapped_column(
        Numeric(24, 6)
    )

    volume: Mapped[int | None] = mapped_column(
        BigInteger
    )

    shares_outstanding: Mapped[Decimal | None] = mapped_column(
        Numeric(24, 4)
    )

    share_data_date: Mapped[date | None] = mapped_column(Date)

    market_cap: Mapped[Decimal | None] = mapped_column(
        Numeric(30, 4)
    )

    price_source: Mapped[str | None] = mapped_column(
        String(50)
    )

    share_source: Mapped[str | None] = mapped_column(
        String(50)
    )

    calculation_method: Mapped[str | None] = mapped_column(
        String(100)
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class TTMFinancial(Base):
    __tablename__ = "ttm_financials"

    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "period_end",
            "statement_scope",
            name="uq_ttm_financial_identity",
        ),
        Index(
            "ix_ttm_financials_company_period",
            "company_id",
            "period_end",
        ),
        Index(
            "ix_ttm_financials_period_end",
            "period_end",
        ),
        Index(
            "ix_ttm_financials_scope_period",
            "statement_scope",
            "period_end",
        ),
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
    )

    company_id: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
    )

    period_end: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        
    )

    statement_scope: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    revenue_ttm: Mapped[Decimal | None] = mapped_column(
        Numeric(24, 4)
    )

    ebitda_ttm: Mapped[Decimal | None] = mapped_column(
        Numeric(24, 4)
    )

    ebit_ttm: Mapped[Decimal | None] = mapped_column(
        Numeric(24, 4)
    )

    profit_before_tax_ttm: Mapped[Decimal | None] = mapped_column(
        Numeric(24, 4)
    )

    net_income_ttm: Mapped[Decimal | None] = mapped_column(
        Numeric(24, 4)
    )

    eps_ttm: Mapped[Decimal | None] = mapped_column(
        Numeric(18, 6)
    )

    operating_cash_flow_ttm: Mapped[Decimal | None] = mapped_column(
        Numeric(24, 4)
    )

    capital_expenditure_ttm: Mapped[Decimal | None] = mapped_column(
        Numeric(24, 4)
    )

    free_cash_flow_ttm: Mapped[Decimal | None] = mapped_column(
        Numeric(24, 4)
    )

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

    calculation_method: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    source_periods: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    source: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="DERIVED",
        server_default="DERIVED",
    )

    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )


class FinancialRatio(Base):
    __tablename__ = "financial_ratios"

    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "period_end",
            "statement_scope",
            name="uq_financial_ratio_identity",
        ),
        Index(
            "ix_financial_ratios_company_period",
            "company_id",
            "period_end",
        ),
        Index(
            "ix_financial_ratios_period",
            "period_end",
        ),
        Index(
            "ix_financial_ratios_scope_period",
            "statement_scope",
            "period_end",
        ),
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )

    company_id: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
    )

    period_end: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        
    )

    statement_scope: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    ebitda_margin: Mapped[Decimal | None] = mapped_column(
        Numeric(18, 6)
    )

    ebit_margin: Mapped[Decimal | None] = mapped_column(
        Numeric(18, 6)
    )

    net_profit_margin: Mapped[Decimal | None] = mapped_column(
        Numeric(18, 6)
    )

    roe: Mapped[Decimal | None] = mapped_column(
        Numeric(18, 6)
    )

    roa: Mapped[Decimal | None] = mapped_column(
        Numeric(18, 6)
    )

    revenue_growth_yoy: Mapped[Decimal | None] = mapped_column(
        Numeric(18, 6)
    )

    ebitda_growth_yoy: Mapped[Decimal | None] = mapped_column(
        Numeric(18, 6)
    )

    ebit_growth_yoy: Mapped[Decimal | None] = mapped_column(
        Numeric(18, 6)
    )

    net_income_growth_yoy: Mapped[Decimal | None] = mapped_column(
        Numeric(18, 6)
    )

    eps_growth_yoy: Mapped[Decimal | None] = mapped_column(
        Numeric(18, 6)
    )

    debt_to_equity: Mapped[Decimal | None] = mapped_column(
        Numeric(18, 6)
    )

    debt_to_ebitda: Mapped[Decimal | None] = mapped_column(
        Numeric(18, 6)
    )

    net_debt_to_ebitda: Mapped[Decimal | None] = mapped_column(
        Numeric(18, 6)
    )

    asset_turnover: Mapped[Decimal | None] = mapped_column(
        Numeric(18, 6)
    )

    eps_ttm: Mapped[Decimal | None] = mapped_column(
        Numeric(18, 6)
    )

    operating_cash_flow_margin: Mapped[Decimal | None] = mapped_column(
        Numeric(18, 6)
    )

    free_cash_flow_margin: Mapped[Decimal | None] = mapped_column(
        Numeric(18, 6)
    )

    fcf_to_net_income: Mapped[Decimal | None] = mapped_column(
        Numeric(18, 6)
    )

    ocf_to_net_income: Mapped[Decimal | None] = mapped_column(
        Numeric(18, 6)
    )

    calculation_method: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    source_period: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )

    prior_period: Mapped[date | None] = mapped_column(Date)

    source: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="DERIVED",
        server_default="DERIVED",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
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

class FinancialRawFiling(Base):
    __tablename__ = "financial_raw_filings"

    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "source_reference",
            "sha256",
            name="uq_financial_raw_filing_identity",
        ),
        Index(
            "ix_financial_raw_filings_company_id",
            "company_id",
        ),
        Index(
            "ix_financial_raw_filings_symbol",
            "symbol",
        ),
        Index(
            "ix_financial_raw_filings_period_end",
            "period_end",
        ),
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )

    company_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("companies.id"),
        nullable=False,
        
    )

    symbol: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    period_end: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )

    statement_scope: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    submission_type: Mapped[str | None] = mapped_column(
        String(50)
    )

    audit_status: Mapped[str | None] = mapped_column(
        String(50)
    )

    source_reference: Mapped[str | None] = mapped_column(
        String(100)
    )

    xbrl_url: Mapped[str | None] = mapped_column(
        Text
    )

    raw_relative_path: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    sha256: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )

    file_size: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
    )

    downloaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    processed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )

    processing_status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="PENDING",
        server_default="PENDING",
    )

    processing_error: Mapped[str | None] = mapped_column(
        Text
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )