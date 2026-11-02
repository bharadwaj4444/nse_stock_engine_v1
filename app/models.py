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
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

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

class ShareholdingSnapshot(Base):
    __tablename__ = "shareholding_snapshots"

    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "effective_date",
            name="uq_shareholding_snapshot_identity",
        ),
        Index(
            "ix_shareholding_snapshot_company_date",
            "company_id",
            "effective_date",
        ),
        Index(
            "ix_shareholding_snapshot_date",
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
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
    )

    effective_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )

    submission_date: Mapped[date | None] = mapped_column(Date)
    revision_date: Mapped[date | None] = mapped_column(Date)
    revised: Mapped[bool] = mapped_column(
        nullable=False,
        default=False,
        server_default="false",
    )

    total_shares: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
    )

    promoter_shares: Mapped[int | None] = mapped_column(BigInteger)
    public_shares: Mapped[int | None] = mapped_column(BigInteger)
    non_promoter_non_public_shares: Mapped[int | None] = mapped_column(BigInteger)

    government_shares: Mapped[int | None] = mapped_column(BigInteger)
    domestic_institutions_shares: Mapped[int | None] = mapped_column(BigInteger)
    foreign_institutions_shares: Mapped[int | None] = mapped_column(BigInteger)
    non_institutions_shares: Mapped[int | None] = mapped_column(BigInteger)

    mutual_funds_shares: Mapped[int | None] = mapped_column(BigInteger)
    venture_capital_funds_shares: Mapped[int | None] = mapped_column(BigInteger)
    alternative_investment_funds_shares: Mapped[int | None] = mapped_column(BigInteger)
    banks_shares: Mapped[int | None] = mapped_column(BigInteger)
    insurance_companies_shares: Mapped[int | None] = mapped_column(BigInteger)
    provident_pension_funds_shares: Mapped[int | None] = mapped_column(BigInteger)
    asset_reconstruction_companies_shares: Mapped[int | None] = mapped_column(BigInteger)
    domestic_sovereign_wealth_funds_shares: Mapped[int | None] = mapped_column(BigInteger)
    nbfc_shares: Mapped[int | None] = mapped_column(BigInteger)
    other_domestic_financial_institutions_shares: Mapped[int | None] = mapped_column(BigInteger)

    fdi_shares: Mapped[int | None] = mapped_column(BigInteger)
    foreign_vc_investors_shares: Mapped[int | None] = mapped_column(BigInteger)
    foreign_sovereign_wealth_funds_shares: Mapped[int | None] = mapped_column(BigInteger)
    fpi_category_i_shares: Mapped[int | None] = mapped_column(BigInteger)
    fpi_category_ii_shares: Mapped[int | None] = mapped_column(BigInteger)
    overseas_depositories_shares: Mapped[int | None] = mapped_column(BigInteger)
    other_foreign_institutions_shares: Mapped[int | None] = mapped_column(BigInteger)

    government_state_shares: Mapped[int | None] = mapped_column(BigInteger)
    government_promoted_companies_shares: Mapped[int | None] = mapped_column(BigInteger)
    governments_shares: Mapped[int | None] = mapped_column(BigInteger)

    associate_companies_subsidiaries_shares: Mapped[int | None] = mapped_column(BigInteger)
    directors_relatives_shares: Mapped[int | None] = mapped_column(BigInteger)
    key_managerial_personnel_shares: Mapped[int | None] = mapped_column(BigInteger)
    promoter_relatives_shares: Mapped[int | None] = mapped_column(BigInteger)
    promoter_related_trusts_shares: Mapped[int | None] = mapped_column(BigInteger)
    iepf_shares: Mapped[int | None] = mapped_column(BigInteger)
    resident_individuals_upto_2l_shares: Mapped[int | None] = mapped_column(BigInteger)
    resident_individuals_above_2l_shares: Mapped[int | None] = mapped_column(BigInteger)
    nris_shares: Mapped[int | None] = mapped_column(BigInteger)
    foreign_nationals_shares: Mapped[int | None] = mapped_column(BigInteger)
    foreign_companies_shares: Mapped[int | None] = mapped_column(BigInteger)
    bodies_corporate_shares: Mapped[int | None] = mapped_column(BigInteger)
    other_non_institutions_shares: Mapped[int | None] = mapped_column(BigInteger)

    shareholding_pattern_shares: Mapped[int | None] = mapped_column(BigInteger)

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

class ValuationMetric(Base):
    __tablename__ = "valuation_metrics"

    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "valuation_date",
            "statement_scope",
            name="uq_valuation_metrics_identity",
        ),
        Index(
            "ix_valuation_metrics_company_date",
            "company_id",
            "valuation_date",
        ),
        Index(
            "ix_valuation_metrics_valuation_date",
            "valuation_date",
        ),
        Index(
            "ix_valuation_metrics_scope_date",
            "statement_scope",
            "valuation_date",
        ),
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )

    company_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
    )

    valuation_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )

    statement_scope: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    # Market value
    market_cap: Mapped[Decimal | None] = mapped_column(
        Numeric(30, 4)
    )

    enterprise_value: Mapped[Decimal | None] = mapped_column(
        Numeric(30, 4)
    )

    # Point-in-time TTM provenance
    ttm_period_end: Mapped[date | None] = mapped_column(Date)

    ttm_filing_date: Mapped[date | None] = mapped_column(Date)

    # Valuation multiples
    pe_ratio: Mapped[Decimal | None] = mapped_column(
        Numeric(24, 6)
    )

    price_to_sales: Mapped[Decimal | None] = mapped_column(
        Numeric(24, 6)
    )

    price_to_fcf: Mapped[Decimal | None] = mapped_column(
        Numeric(24, 6)
    )

    ev_to_ebitda: Mapped[Decimal | None] = mapped_column(
        Numeric(24, 6)
    )

    ev_to_sales: Mapped[Decimal | None] = mapped_column(
        Numeric(24, 6)
    )

    # Valuation yields
    earnings_yield: Mapped[Decimal | None] = mapped_column(
        Numeric(24, 6)
    )

    fcf_yield: Mapped[Decimal | None] = mapped_column(
        Numeric(24, 6)
    )

    # Provenance
    calculation_method: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

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

    latest_filing_date: Mapped[date | None] = mapped_column(
        Date,
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

    filing_date: Mapped[date | None] = mapped_column(Date)
    
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

class ShareholdingMetrics(Base):
    __tablename__ = "shareholding_metrics"

    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "effective_date",
            name="uq_shareholding_metrics_identity",
        ),
        Index(
            "ix_shareholding_metrics_company_date",
            "company_id",
            "effective_date",
        ),
        Index(
            "ix_shareholding_metrics_date",
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
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
    )

    effective_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )

    total_shares: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
    )

    promoter_pct: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 6)
    )

    public_pct: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 6)
    )

    non_promoter_non_public_pct: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 6)
    )

    government_pct: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 6)
    )

    domestic_institutions_pct: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 6)
    )

    foreign_institutions_pct: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 6)
    )

    non_institutions_pct: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 6)
    )

    mutual_funds_pct: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 6)
    )

    venture_capital_funds_pct: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 6)
    )

    alternative_investment_funds_pct: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 6)
    )

    banks_pct: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 6)
    )

    insurance_companies_pct: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 6)
    )

    provident_pension_funds_pct: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 6)
    )

    fdi_pct: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 6)
    )

    foreign_vc_investors_pct: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 6)
    )

    foreign_sovereign_wealth_funds_pct: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 6)
    )

    fpi_category_i_pct: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 6)
    )

    fpi_category_ii_pct: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 6)
    )

    overseas_depositories_pct: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 6)
    )

    resident_individuals_upto_2l_pct: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 6)
    )

    resident_individuals_above_2l_pct: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 6)
    )

    nris_pct: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 6)
    )

    foreign_nationals_pct: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 6)
    )

    foreign_companies_pct: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 6)
    )

    bodies_corporate_pct: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 6)
    )

    other_non_institutions_pct: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 6)
    )

    source: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="NSE",
        server_default="NSE",
    )

    calculation_method: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        default="NSE_SHAREHOLDING_PERCENTAGE",
        server_default="NSE_SHAREHOLDING_PERCENTAGE",
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

class VerificationRun(Base):
    __tablename__ = "verification_runs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    trade_date: Mapped[date] = mapped_column(Date, nullable=False)
    trigger: Mapped[str] = mapped_column(String(20), nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    completed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    failure_count: Mapped[int] = mapped_column(Integer, nullable=False)
    warning_count: Mapped[int] = mapped_column(Integer, nullable=False)
    check_count: Mapped[int] = mapped_column(Integer, nullable=False)

    results: Mapped[list["VerificationResult"]] = relationship(
        back_populates="run",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    __table_args__ = (
        Index(
            "ix_verification_runs_trade_date_started_at",
            "trade_date",
            "started_at",
        ),
    )

class VerificationResult(Base):
    __tablename__ = "verification_results"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("verification_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    check_name: Mapped[str] = mapped_column(String(150), nullable=False)
    status: Mapped[str] = mapped_column(String(10), nullable=False)
    expected: Mapped[int | None] = mapped_column(Integer, nullable=True)
    actual: Mapped[int | None] = mapped_column(Integer, nullable=True)
    details: Mapped[str] = mapped_column(Text, nullable=False, default="")

    run: Mapped["VerificationRun"] = relationship(back_populates="results")

    __table_args__ = (
        UniqueConstraint(
            "run_id",
            "check_name",
            name="uq_verification_results_run_check",
        ),
        Index("ix_verification_results_run_id", "run_id"),
    )


class HoldDecision(Base):
    __tablename__ = "hold_decisions"

    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "trade_date",
            name="uq_hold_decisions_company_trade_date",
        ),
        Index(
            "ix_hold_decisions_trade_date",
            "trade_date",
        ),
        Index(
            "ix_hold_decisions_company_trade_date",
            "company_id",
            "trade_date",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
    )
    trade_date: Mapped[date] = mapped_column(Date, nullable=False)
    action: Mapped[str] = mapped_column(String(20), nullable=False)
    score: Mapped[Decimal | None] = mapped_column(Numeric(10, 6))
    red_green: Mapped[str] = mapped_column(String(20), nullable=False, default="needs_data")
    action_reason: Mapped[str] = mapped_column(String(50), nullable=False, default="missing_score")
    hold_until: Mapped[date | None] = mapped_column(Date)
    sell_target_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    sell_target_date: Mapped[date | None] = mapped_column(Date)
    expected_return: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))

    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class Outcome(Base):
    __tablename__ = "outcomes"

    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "trade_date",
            name="uq_outcomes_company_trade_date",
        ),
        Index(
            "ix_outcomes_trade_date",
            "trade_date",
        ),
        Index(
            "ix_outcomes_company_trade_date",
            "company_id",
            "trade_date",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
    )
    trade_date: Mapped[date] = mapped_column(Date, nullable=False)
    expected_return: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    actual_return: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    deviation: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")

    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class NewsSignal(Base):
    __tablename__ = "news_signals"

    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "trade_date",
            "source",
            name="uq_news_signals_company_date_source",
        ),
        Index(
            "ix_news_signals_trade_date",
            "trade_date",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
    )
    trade_date: Mapped[date] = mapped_column(Date, nullable=False)
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    sentiment: Mapped[str] = mapped_column(String(20), nullable=False, default="neutral")
    score_adjustment: Mapped[Decimal | None] = mapped_column(Numeric(10, 6))
    significance: Mapped[str] = mapped_column(String(20), nullable=False, default="unknown")

    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class Override(Base):
    __tablename__ = "overrides"

    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "trade_date",
            "source",
            name="uq_overrides_company_date_source",
        ),
        Index(
            "ix_overrides_trade_date",
            "trade_date",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
    )
    trade_date: Mapped[date] = mapped_column(Date, nullable=False)
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    sentiment: Mapped[str] = mapped_column(String(20), nullable=False, default="neutral")
    original_score: Mapped[Decimal | None] = mapped_column(Numeric(10, 6))
    adjusted_score: Mapped[Decimal | None] = mapped_column(Numeric(10, 6))
    adjustment: Mapped[Decimal | None] = mapped_column(Numeric(10, 6))
    significance_status: Mapped[str] = mapped_column(String(20), nullable=False, default="unknown")
    applied: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")

    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )