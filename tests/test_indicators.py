import pandas as pd
import numpy as np
from app.indicators import calculate

def test_indicators_basic():
    n = 300
    dates = pd.date_range("2025-01-01", periods=n, freq="D")
    close = pd.Series(np.linspace(100, 200, n))
    df = pd.DataFrame({
        "trade_date": dates.date,
        "open": close - 1,
        "high": close + 2,
        "low": close - 2,
        "close": close,
        "volume": 100000,
    })
    out = calculate(df)
    assert out["sma20"].notna().sum() == n - 19
    assert out["sma200"].notna().sum() == n - 199
    assert out["return_252d"].notna().sum() == n - 252
