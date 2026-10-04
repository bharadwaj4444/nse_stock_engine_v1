from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db import SessionLocal


FEATURE_SQL = text(
    """
    INSERT INTO historical_features (
        company_id,
        trade_date,

        close_price,
        volume,
        market_cap,

        return_5d,
        return_20d,
        return_60d,
        return_120d,
        return_252d,

        sma20,
        sma50,
        sma200,
        ema20,
        ema50,

        rsi14,
        macd,
        macd_signal,
        macd_histogram,
        atr14,
        adx14,
        volatility20,
        volatility60,
        relative_volume20,

        nifty_relative_20d,
        nifty_relative_60d,

        ttm_period_end,
        ttm_filing_date,

        ebitda_margin,
        ebit_margin,
        net_profit_margin,
        roe,
        roa,

        debt_to_equity,
        debt_to_ebitda,
        net_debt_to_ebitda,
        asset_turnover,
        eps_ttm,

        pe_ratio,
        price_to_sales,
        price_to_fcf,
        ev_to_ebitda,
        ev_to_sales,
        earnings_yield,
        fcf_yield,

        statement_scope,
        calculation_method
    )
    SELECT
        mm.company_id,
        mm.trade_date,

        mm.close_price,
        mm.volume,
        mm.market_cap,

        ti.return_5d,
        ti.return_20d,
        ti.return_60d,
        ti.return_120d,
        ti.return_252d,

        ti.sma20,
        ti.sma50,
        ti.sma200,
        ti.ema20,
        ti.ema50,

        ti.rsi14,
        ti.macd,
        ti.macd_signal,
        ti.macd_histogram,
        ti.atr14,
        ti.adx14,
        ti.volatility20,
        ti.volatility60,
        ti.relative_volume20,

        ti.nifty_relative_20d,
        ti.nifty_relative_60d,

        t.period_end,
        t.latest_filing_date,

        r.ebitda_margin,
        r.ebit_margin,
        r.net_profit_margin,
        r.roe,
        r.roa,

        r.debt_to_equity,
        r.debt_to_ebitda,
        r.net_debt_to_ebitda,
        r.asset_turnover,
        r.eps_ttm,

        v.pe_ratio,
        v.price_to_sales,
        v.price_to_fcf,
        v.ev_to_ebitda,
        v.ev_to_sales,
        v.earnings_yield,
        v.fcf_yield,

        'Consolidated',
        'PIT_MARKET_TTM_RATIO_VALUATION'
    FROM market_metrics mm

    LEFT JOIN technical_indicators ti
        ON ti.company_id = mm.company_id
       AND ti.trade_date = mm.trade_date

    LEFT JOIN LATERAL (
        SELECT
            t.*
        FROM ttm_financials t
        WHERE t.company_id = mm.company_id
          AND t.statement_scope = 'Consolidated'
          AND t.latest_filing_date <= mm.trade_date
        ORDER BY
            t.period_end DESC,
            t.latest_filing_date DESC,
            t.id DESC
        LIMIT 1
    ) t ON TRUE

    LEFT JOIN financial_ratios r
        ON r.company_id = t.company_id
       AND r.period_end = t.period_end
       AND r.statement_scope = 'Consolidated'

    LEFT JOIN valuation_metrics v
        ON v.company_id = mm.company_id
       AND v.valuation_date = mm.trade_date
       AND v.statement_scope = 'Consolidated'

    WHERE mm.trade_date BETWEEN :start_date AND :end_date

    ON CONFLICT (
        company_id,
        trade_date,
        statement_scope
    )
    DO UPDATE SET
        close_price = EXCLUDED.close_price,
        volume = EXCLUDED.volume,
        market_cap = EXCLUDED.market_cap,

        return_5d = EXCLUDED.return_5d,
        return_20d = EXCLUDED.return_20d,
        return_60d = EXCLUDED.return_60d,
        return_120d = EXCLUDED.return_120d,
        return_252d = EXCLUDED.return_252d,

        sma20 = EXCLUDED.sma20,
        sma50 = EXCLUDED.sma50,
        sma200 = EXCLUDED.sma200,
        ema20 = EXCLUDED.ema20,
        ema50 = EXCLUDED.ema50,

        rsi14 = EXCLUDED.rsi14,
        macd = EXCLUDED.macd,
        macd_signal = EXCLUDED.macd_signal,
        macd_histogram = EXCLUDED.macd_histogram,
        atr14 = EXCLUDED.atr14,
        adx14 = EXCLUDED.adx14,
        volatility20 = EXCLUDED.volatility20,
        volatility60 = EXCLUDED.volatility60,
        relative_volume20 = EXCLUDED.relative_volume20,

        nifty_relative_20d = EXCLUDED.nifty_relative_20d,
        nifty_relative_60d = EXCLUDED.nifty_relative_60d,

        ttm_period_end = EXCLUDED.ttm_period_end,
        ttm_filing_date = EXCLUDED.ttm_filing_date,

        ebitda_margin = EXCLUDED.ebitda_margin,
        ebit_margin = EXCLUDED.ebit_margin,
        net_profit_margin = EXCLUDED.net_profit_margin,
        roe = EXCLUDED.roe,
        roa = EXCLUDED.roa,

        debt_to_equity = EXCLUDED.debt_to_equity,
        debt_to_ebitda = EXCLUDED.debt_to_ebitda,
        net_debt_to_ebitda = EXCLUDED.net_debt_to_ebitda,
        asset_turnover = EXCLUDED.asset_turnover,
        eps_ttm = EXCLUDED.eps_ttm,

        pe_ratio = EXCLUDED.pe_ratio,
        price_to_sales = EXCLUDED.price_to_sales,
        price_to_fcf = EXCLUDED.price_to_fcf,
        ev_to_ebitda = EXCLUDED.ev_to_ebitda,
        ev_to_sales = EXCLUDED.ev_to_sales,
        earnings_yield = EXCLUDED.earnings_yield,
        fcf_yield = EXCLUDED.fcf_yield,

        calculation_method = EXCLUDED.calculation_method,
        updated_at = CURRENT_TIMESTAMP
    """
)


COUNT_SQL = text(
    """
    SELECT COUNT(*)
    FROM historical_features
    WHERE trade_date BETWEEN :start_date AND :end_date
    """
)


LEAKAGE_SQL = text(
    """
    SELECT COUNT(*)
    FROM historical_features
    WHERE trade_date BETWEEN :start_date AND :end_date
      AND ttm_filing_date > trade_date
    """
)


def build_historical_features(
    start_date: date,
    end_date: date,
    *,
    session: Session | None = None,
) -> int:
    """
    Build point-in-time historical features.

    Each feature row represents one company/trading-date pair.

    Fundamental data is selected using:
        latest_filing_date <= trade_date

    Valuation data is selected using:
        valuation_date = trade_date
    """

    own_session = session is None

    if own_session:
        session = SessionLocal()

    try:
        result = session.execute(
            FEATURE_SQL,
            {
                "start_date": start_date,
                "end_date": end_date,
            },
        )

        session.commit()

        count = session.execute(
            COUNT_SQL,
            {
                "start_date": start_date,
                "end_date": end_date,
            },
        ).scalar_one()

        leakage = session.execute(
            LEAKAGE_SQL,
            {
                "start_date": start_date,
                "end_date": end_date,
            },
        ).scalar_one()

        if leakage:
            raise RuntimeError(
                f"PIT leakage detected: {leakage} rows have "
                "ttm_filing_date > trade_date"
            )

        return int(count)

    except Exception:
        session.rollback()
        raise

    finally:
        if own_session:
            session.close()