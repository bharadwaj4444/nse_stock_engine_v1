from datetime import date

from fastapi import FastAPI, HTTPException
from sqlalchemy import select, text

from app.adapters.outbound.persistence import RecommendationPersistenceAdapter
from app.db import engine, SessionLocal
from app.models import Company, DailyPrice, TechnicalIndicator
from app.fundamental_analysis import (
    get_fundamental_analysis,
    get_fundamental_history,
)

app = FastAPI(title="NSE Stock Engine V1")


@app.get("/health")
def health():
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    return {"status": "ok"}


@app.get("/")
def root():
    return {
        "service": "nse-stock-engine",
        "version": "0.1.0",
        "endpoints": [
            "/health",
            "/fundamentals/{symbol}",
            "/fundamentals/{symbol}/history",
            "/stocks/{symbol}",
            "/recommendations/red-green",
            "/recommendations/holds",
        ],
    }


@app.get("/fundamentals/{symbol}")
def fundamentals(
    symbol: str,
    period_end: date | None = None,
    period_type: str = "quarterly",
    statement_scope: str = "Consolidated",
    as_of_date: date | None = None,
):
    try:
        return get_fundamental_analysis(
            symbol=symbol,
            period_end=period_end,
            period_type=period_type,
            statement_scope=statement_scope,
            as_of_date=as_of_date,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@app.get("/fundamentals/{symbol}/history")
def fundamental_history(
    symbol: str,
    period_type: str = "quarterly",
    statement_scope: str = "Consolidated",
):
    try:
        return get_fundamental_history(
            symbol=symbol,
            period_type=period_type,
            statement_scope=statement_scope,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@app.get("/stocks/{symbol}")
def stock_analysis(
    symbol: str,
    period_end: date | None = None,
    statement_scope: str = "Consolidated",
):
    symbol = symbol.upper()

    with SessionLocal() as db:
        company = db.scalar(
            select(Company).where(Company.nse_symbol == symbol)
        )

        if company is None:
            raise HTTPException(
                status_code=404,
                detail=f"Company not found: {symbol}",
            )

        price = db.scalar(
            select(DailyPrice)
            .where(DailyPrice.company_id == company.id)
            .order_by(DailyPrice.trade_date.desc())
        )

        indicator = db.scalar(
            select(TechnicalIndicator)
            .where(TechnicalIndicator.company_id == company.id)
            .order_by(TechnicalIndicator.trade_date.desc())
        )

        if price is None:
            raise HTTPException(
                status_code=404,
                detail=f"No market data found for {symbol}",
            )

        if indicator is None:
            raise HTTPException(
                status_code=404,
                detail=f"No technical indicators found for {symbol}",
            )

    fundamentals_data = get_fundamental_analysis(
        symbol=symbol,
        period_end=period_end,
        period_type="quarterly",
        statement_scope=statement_scope,
    )

    def value(obj, field):
        return getattr(obj, field, None)

    technical = {
        "trade_date": indicator.trade_date,
        "sma20": value(indicator, "sma20"),
        "sma50": value(indicator, "sma50"),
        "sma100": value(indicator, "sma100"),
        "sma200": value(indicator, "sma200"),
        "ema20": value(indicator, "ema20"),
        "ema50": value(indicator, "ema50"),
        "rsi14": value(indicator, "rsi14"),
        "macd": value(indicator, "macd"),
        "macd_signal": value(indicator, "macd_signal"),
        "macd_histogram": value(indicator, "macd_histogram"),
        "atr14": value(indicator, "atr14"),
        "bb_upper": value(indicator, "bb_upper"),
        "bb_middle": value(indicator, "bb_middle"),
        "bb_lower": value(indicator, "bb_lower"),
        "adx14": value(indicator, "adx14"),
        "volatility20": value(indicator, "volatility20"),
        "volatility60": value(indicator, "volatility60"),
        "return_1d": value(indicator, "return_1d"),
        "return_5d": value(indicator, "return_5d"),
        "return_20d": value(indicator, "return_20d"),
        "return_60d": value(indicator, "return_60d"),
        "return_120d": value(indicator, "return_120d"),
        "return_252d": value(indicator, "return_252d"),
        "relative_volume20": value(indicator, "relative_volume20"),
        "nifty_relative_20d": value(indicator, "nifty_relative_20d"),
        "nifty_relative_60d": value(indicator, "nifty_relative_60d"),
    }

    return {
        "company": {
            "symbol": company.nse_symbol,
            "name": company.company_name,
            "isin": company.isin,
            "series": company.series,
            "status": company.status,
        },
        "market": {
            "trade_date": price.trade_date,
            "open": price.open_price,
            "high": price.high_price,
            "low": price.low_price,
            "close": price.close_price,
            "previous_close": price.prev_close,
            "volume": price.volume,
            "traded_value": price.traded_value,
            "trades_count": price.trades_count,
            "delivery_quantity": price.delivery_qty,
            "delivery_percentage": price.delivery_pct,
            "vwap": price.vwap,
        },
        "technical": technical,
        "fundamentals": fundamentals_data,
    }


@app.get("/recommendations/red-green")
def red_green_recommendations(
    trade_date: date | None = None,
):
    """
    Deliver red/green-scored recommendations.

    The API returns the score in %; the UI maps the score to red/green.
    """

    target_date = trade_date or date.today()

    with SessionLocal() as session:
        ranking_store = RecommendationPersistenceAdapter(session)
        scored = ranking_store.get_rankings(
            trade_date=target_date,
            statement_scope="Consolidated",
        )

    recommendations = []

    for instrument in scored:
        recommendations.append({
            "company_id": instrument.company_id,
            "trade_date": instrument.trade_date,
            "score": instrument.score,
            "red_green": instrument.red_green,
        })

    return {
        "trade_date": target_date,
        "red_green_threshold": 50.0,
        "recommendations": recommendations,
    }


@app.get("/recommendations/holds")
def hold_decisions(
    trade_date: date | None = None,
):
    """
    Deliver engine-decided holds for a ranking cycle.
    """

    target_date = trade_date or date.today()

    with SessionLocal() as session:
        hold_store = RecommendationPersistenceAdapter(session)
        decisions = hold_store.get_hold_decisions(trade_date=target_date)

    holds = []

    for decision in decisions:
        holds.append({
            "company_id": decision.company_id,
            "trade_date": decision.trade_date,
            "action": decision.action,
            "score": decision.score,
            "red_green": decision.red_green,
            "action_reason": decision.action_reason,
            "hold_until": decision.hold_until,
            "sell_target_price": decision.sell_target_price,
            "sell_target_date": decision.sell_target_date,
            "expected_return": decision.expected_return,
        })

    return {
        "trade_date": target_date,
        "holds": holds,
    }