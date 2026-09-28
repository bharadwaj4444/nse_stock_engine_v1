from __future__ import annotations

import math
from datetime import date
import numpy as np
import pandas as pd
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.db import SessionLocal
from app.models import BenchmarkPrice, Company, DailyPrice, TechnicalIndicator

def sma(s, n): return s.rolling(n, min_periods=n).mean()
def ema(s, n): return s.ewm(span=n, adjust=False, min_periods=n).mean()

def rsi_wilder(close, n=14):
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1/n, adjust=False, min_periods=n).mean()
    avg_loss = loss.ewm(alpha=1/n, adjust=False, min_periods=n).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    out = 100 - (100 / (1 + rs))
    out = out.where(avg_loss.ne(0), 100)
    return out

def atr_wilder(df, n=14):
    prev = df["close"].shift(1)
    tr = pd.concat([
        df["high"] - df["low"],
        (df["high"] - prev).abs(),
        (df["low"] - prev).abs()
    ], axis=1).max(axis=1)
    return tr.ewm(alpha=1/n, adjust=False, min_periods=n).mean()

def adx_wilder(df, n=14):
    high, low, close = df["high"], df["low"], df["close"]
    up = high.diff()
    down = -low.diff()
    plus_dm = up.where((up > down) & (up > 0), 0.0)
    minus_dm = down.where((down > up) & (down > 0), 0.0)
    prev = close.shift(1)
    tr = pd.concat([high-low, (high-prev).abs(), (low-prev).abs()], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1/n, adjust=False, min_periods=n).mean()
    plus_di = 100 * plus_dm.ewm(alpha=1/n, adjust=False, min_periods=n).mean() / atr
    minus_di = 100 * minus_dm.ewm(alpha=1/n, adjust=False, min_periods=n).mean() / atr
    denom = (plus_di + minus_di).replace(0, np.nan)
    dx = 100 * (plus_di - minus_di).abs() / denom
    return dx.ewm(alpha=1/n, adjust=False, min_periods=n).mean()

def calculate(df: pd.DataFrame, nifty: pd.Series | None = None) -> pd.DataFrame:
    df = df.sort_values("trade_date").copy()
    c = df["close"].astype(float)
    h = df["high"].astype(float)
    l = df["low"].astype(float)
    v = df["volume"].astype(float)

    out = pd.DataFrame({"trade_date": df["trade_date"]})
    out["sma20"] = sma(c,20); out["sma50"] = sma(c,50)
    out["sma100"] = sma(c,100); out["sma200"] = sma(c,200)
    out["ema20"] = ema(c,20); out["ema50"] = ema(c,50)
    out["rsi14"] = rsi_wilder(c,14)

    e12, e26 = ema(c,12), ema(c,26)
    out["macd"] = e12 - e26
    out["macd_signal"] = ema(out["macd"],9)
    out["macd_histogram"] = out["macd"] - out["macd_signal"]

    out["atr14"] = atr_wilder(pd.DataFrame({"high":h,"low":l,"close":c}),14)

    mid = sma(c,20)
    std = c.rolling(20, min_periods=20).std(ddof=0)
    out["bb_middle"] = mid
    out["bb_upper"] = mid + 2*std
    out["bb_lower"] = mid - 2*std

    out["adx14"] = adx_wilder(pd.DataFrame({"high":h,"low":l,"close":c}),14)

    returns = c.pct_change()
    out["volatility20"] = returns.rolling(20, min_periods=20).std() * math.sqrt(252)
    out["volatility60"] = returns.rolling(60, min_periods=60).std() * math.sqrt(252)

    for n in [1,5,20,60,120,252]:
        out[f"return_{n}d"] = c.pct_change(n)

    out["relative_volume20"] = v / v.rolling(20, min_periods=20).mean()

    if nifty is not None:
        stock_dates = pd.to_datetime(df["trade_date"])

        stock_close = pd.Series(
            c.to_numpy(),
            index=stock_dates
        )

        nifty_close = nifty.copy()
        nifty_close.index = pd.to_datetime(nifty_close.index)
        nifty_close = nifty_close.sort_index()

        aligned = pd.concat(
            [
                stock_close.rename("stock"),
                nifty_close.rename("nifty"),
            ],
            axis=1,
            join="inner",
        ).sort_index()

        stock20 = aligned["stock"].pct_change(20)
        nifty20 = aligned["nifty"].pct_change(20)

        stock60 = aligned["stock"].pct_change(60)
        nifty60 = aligned["nifty"].pct_change(60)

        relative20 = stock20 - nifty20
        relative60 = stock60 - nifty60

        out["nifty_relative_20d"] = (
            relative20.reindex(stock_dates).to_numpy()
        )

        out["nifty_relative_60d"] = (
            relative60.reindex(stock_dates).to_numpy()
        )

    return out.replace([np.inf, -np.inf], np.nan)

def calculate_for_date(target=None):
    if target is None:
        target = date.today()

    with SessionLocal() as db:
        # Load NIFTY 50 benchmark close prices once.
        benchmark_rows = (
            db.query(BenchmarkPrice)
            .filter(
                BenchmarkPrice.benchmark == "NIFTY50",
                BenchmarkPrice.trade_date <= target,
            )
            .order_by(BenchmarkPrice.trade_date)
            .all()
        )

        nifty = None

        if benchmark_rows:
            nifty = pd.Series(
                {
                    pd.Timestamp(row.trade_date): float(row.close_price)
                    for row in benchmark_rows
                    if row.close_price is not None
                }
            ).sort_index()

        companies = (
            db.query(Company)
            .filter(Company.is_active.is_(True))
            .all()
        )

        for company in companies:
            prices = (
                db.query(DailyPrice)
                .filter(
                    DailyPrice.company_id == company.id,
                    DailyPrice.trade_date <= target,
                )
                .order_by(DailyPrice.trade_date.desc())
                .limit(550)
                .all()
            )

            if not prices:
                continue

            prices.reverse()

            df = pd.DataFrame(
                [
                    {
                        "trade_date": p.trade_date,
                        "open": float(p.open_price),
                        "high": float(p.high_price),
                        "low": float(p.low_price),
                        "close": float(p.close_price),
                        "volume": float(p.volume or 0),
                    }
                    for p in prices
                ]
            )

            df["trade_date"] = pd.to_datetime(df["trade_date"])
            df = df.sort_values("trade_date")

            result = calculate(df, nifty=nifty)

            row = result.iloc[-1]

            existing = (
                db.query(TechnicalIndicator)
                .filter(
                    TechnicalIndicator.company_id == company.id,
                    TechnicalIndicator.trade_date == target,
                )
                .one_or_none()
            )

            values = {
                "company_id": company.id,
                "trade_date": target,

                "sma20": row.get("sma20"),
                "sma50": row.get("sma50"),
                "sma100": row.get("sma100"),
                "sma200": row.get("sma200"),

                "ema20": row.get("ema20"),
                "ema50": row.get("ema50"),

                "rsi14": row.get("rsi14"),

                "macd": row.get("macd"),
                "macd_signal": row.get("macd_signal"),
                "macd_histogram": row.get("macd_histogram"),

                "atr14": row.get("atr14"),

                "bb_upper": row.get("bb_upper"),
                "bb_middle": row.get("bb_middle"),
                "bb_lower": row.get("bb_lower"),

                "adx14": row.get("adx14"),

                "volatility20": row.get("volatility20"),
                "volatility60": row.get("volatility60"),

                "return_1d": row.get("return_1d"),
                "return_5d": row.get("return_5d"),
                "return_20d": row.get("return_20d"),
                "return_60d": row.get("return_60d"),
                "return_120d": row.get("return_120d"),
                "return_252d": row.get("return_252d"),

                "relative_volume20": row.get("relative_volume20"),

                "nifty_relative_20d": row.get("nifty_relative_20d"),
                "nifty_relative_60d": row.get("nifty_relative_60d"),
            }

            if existing:
                for key, value in values.items():
                    if key not in ("company_id", "trade_date"):
                        setattr(existing, key, value)
            else:
                db.add(TechnicalIndicator(**values))

        db.commit()