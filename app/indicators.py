from __future__ import annotations

import math
from datetime import date
import numpy as np
import pandas as pd
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.db import SessionLocal
from app.models import Company, DailyPrice, TechnicalIndicator

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
        nr = nifty.sort_index().pct_change()
        sr = c.copy()
        sr.index = pd.to_datetime(df["trade_date"])
        nr = nr.reindex(sr.index)
        stock20 = (1 + sr.pct_change()).rolling(20).apply(np.prod, raw=True) - 1
        nifty20 = (1 + nr).rolling(20).apply(np.prod, raw=True) - 1
        stock60 = (1 + sr.pct_change()).rolling(60).apply(np.prod, raw=True) - 1
        nifty60 = (1 + nr).rolling(60).apply(np.prod, raw=True) - 1
        out["nifty_relative_20d"] = stock20.to_numpy() - nifty20.to_numpy()
        out["nifty_relative_60d"] = stock60.to_numpy() - nifty60.to_numpy()

    return out.replace([np.inf, -np.inf], np.nan)

def calculate_for_date(target: date | None = None):
    with SessionLocal() as db:
        companies = db.scalars(select(Company).where(Company.is_active.is_(True))).all()
        # Need ~1 trading year + 200-day warmup. 300 trading rows is enough.
        for company in companies:
            rows = db.scalars(
                select(DailyPrice)
                .where(DailyPrice.company_id == company.id)
                .order_by(DailyPrice.trade_date.desc())
                .limit(550)
            ).all()
            if not rows:
                continue
            rows.reverse()
            df = pd.DataFrame([{
                "trade_date": r.trade_date,
                "open": float(r.open_price) if r.open_price is not None else np.nan,
                "high": float(r.high_price) if r.high_price is not None else np.nan,
                "low": float(r.low_price) if r.low_price is not None else np.nan,
                "close": float(r.close_price) if r.close_price is not None else np.nan,
                "volume": float(r.volume) if r.volume is not None else np.nan,
            } for r in rows])
            if target is not None:
                df = df[df.trade_date <= target]
            if len(df) < 20:
                continue
            out = calculate(df)
            records = []
            for row in out.itertuples(index=False):
                d = row.trade_date
                if target is not None and d != target:
                    continue
                rec = {"company_id": company.id, "trade_date": d}
                for col in out.columns:
                    if col == "trade_date": continue
                    value = getattr(row, col)
                    rec[col] = None if pd.isna(value) else float(value)
                records.append(rec)
            if records:
                stmt = insert(TechnicalIndicator).values(records)
                cols = [c for c in records[0] if c not in ("company_id","trade_date")]
                stmt = stmt.on_conflict_do_update(
                    index_elements=["company_id","trade_date"],
                    set_={c: getattr(stmt.excluded,c) for c in cols}
                )
                db.execute(stmt)
            db.commit()
