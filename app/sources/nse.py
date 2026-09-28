from __future__ import annotations

import io
import re
import time
import zipfile
from datetime import date
from pathlib import Path

import httpx
import pandas as pd
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import settings

NSE_HOME = "https://www.nseindia.com"
UNIVERSE_URL = "https://nsearchives.nseindia.com/content/equities/EQUITY_L.csv"

def archive_url(trade_date: date) -> str:
    ds = trade_date.strftime("%Y%m%d")
    return f"https://nsearchives.nseindia.com/content/cm/BhavCopy_NSE_CM_0_0_0_{ds}_F_0000.csv.zip"

class NSEClient:
    def __init__(self):
        self.client = httpx.Client(
            timeout=settings.nse_timeout_seconds,
            follow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                              "AppleWebKit/537.36 Chrome/153 Safari/537.36",
                "Accept": "*/*",
                "Accept-Language": "en-US,en;q=0.9",
                "Referer": NSE_HOME + "/",
            },
        )
        self.client.get(NSE_HOME)
        self._last_request = 0.0

    def _throttle(self):
        elapsed = time.monotonic() - self._last_request
        wait = settings.nse_throttle_seconds - elapsed
        if wait > 0:
            time.sleep(wait)

    @retry(stop=stop_after_attempt(settings.nse_max_retries),
           wait=wait_exponential(multiplier=1, min=1, max=10),
           reraise=True)
    def get_bytes(self, url: str) -> bytes:
        self._throttle()
        r = self.client.get(url)
        self._last_request = time.monotonic()
        r.raise_for_status()
        return r.content

    def universe(self) -> pd.DataFrame:
        data = self.get_bytes(UNIVERSE_URL)
        # NSE publishes the equity-segment securities list as CSV.
        df = pd.read_csv(io.BytesIO(data))
        if df.empty:
            raise RuntimeError("NSE universe CSV returned no rows")
        return normalize_universe(df)

    def bhavcopy(self, trade_date: date) -> tuple[pd.DataFrame, str, bytes]:
        url = archive_url(trade_date)
        content = self.get_bytes(url)
        with zipfile.ZipFile(io.BytesIO(content)) as z:
            csv_names = [n for n in z.namelist() if n.lower().endswith(".csv")]
            if not csv_names:
                raise RuntimeError(f"No CSV found inside {url}")
            name = csv_names[0]
            with z.open(name) as f:
                df = pd.read_csv(f)
        return normalize_bhavcopy(df), url, content

    def nifty50_history(self, from_date: date, to_date: date) -> list[dict]:
        import json

        page_url = "https://www.niftyindices.com/reports/historical-data"
        api_url = (
            "https://www.niftyindices.com/"
            "Backpage.aspx/getHistoricaldatatabletoString"
        )

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/153.0.0.0 Safari/537.36"
            ),
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Accept-Language": "en-US,en;q=0.9",
            "Content-Type": "application/json; charset=UTF-8",
            "X-Requested-With": "XMLHttpRequest",
            "Referer": page_url,
        }

        # Bootstrap the session so the site can issue its cookies.
        page_response = self.client.get(
            page_url,
            headers=headers,
            timeout=15.0,
        )

        payload = {
            "cinfo": (
                f"{{'name':'NIFTY 50',"
                f"'startDate':'{from_date.strftime('%d-%b-%Y')}',"
                f"'endDate':'{to_date.strftime('%d-%b-%Y')}',"
                f"'indexName':'NIFTY 50'}}"
            )
        }

        response = self.client.post(
            api_url,
            headers=headers,
            json=payload,
            timeout=60.0,
        )

        response.raise_for_status()

        content_type = response.headers.get("content-type", "")

        if "json" not in content_type.lower():
            raise RuntimeError(
                "NIFTY API returned non-JSON response: "
                f"HTTP {response.status_code}, "
                f"Content-Type={content_type}, "
                f"Body={response.text[:500]!r}"
            )

        body = response.json()
        data = body.get("d", [])

        if isinstance(data, str):
            data = json.loads(data)

        if not data:
            raise RuntimeError(
                f"No NIFTY 50 historical data returned for "
                f"{from_date} to {to_date}"
            )

        return data

def _first(df, candidates):
    lower = {str(c).strip().lower(): c for c in df.columns}
    for c in candidates:
        if c.lower() in lower:
            return lower[c.lower()]
    return None

def normalize_universe(df: pd.DataFrame) -> pd.DataFrame:
    # Current EQUITY_L.csv commonly contains:
    # SYMBOL, NAME OF COMPANY, SERIES, DATE OF LISTING, PAID UP VALUE,
    # MARKET LOT, ISIN NUMBER, FACE VALUE.
    sym = _first(df, ["SYMBOL"])
    isin = _first(df, ["ISIN NUMBER", "ISIN"])
    name = _first(df, ["NAME OF COMPANY", "COMPANY NAME", "NAME"])
    series = _first(df, ["SERIES"])
    listing = _first(df, ["DATE OF LISTING"])
    if not sym:
        raise RuntimeError(f"Cannot find SYMBOL column. Columns={list(df.columns)}")
    out = pd.DataFrame({
        "nse_symbol": df[sym].astype(str).str.strip(),
        "isin": df[isin].astype(str).str.strip() if isin else None,
        "company_name": df[name].astype(str).str.strip() if name else df[sym].astype(str).str.strip(),
        "series": df[series].astype(str).str.strip() if series else None,
    })
    if listing:
        out["listing_date"] = pd.to_datetime(df[listing], errors="coerce").dt.date
    else:
        out["listing_date"] = None
    out = out.drop_duplicates("nse_symbol")
    out = out[out["nse_symbol"].ne("")]
    return out

def normalize_bhavcopy(df: pd.DataFrame) -> pd.DataFrame:
    # UDiFF field names expected in the current CM common bhavcopy.
    aliases = {
        "symbol": ["TckrSymb", "SYMBOL", "Symbol"],
        "series": ["SctySrs", "SERIES", "Series"],
        "open": ["OpnPric", "OPEN", "Open"],
        "high": ["HghPric", "HIGH", "High"],
        "low": ["LwPric", "LOW", "Low"],
        "close": ["ClsPric", "CLOSE", "Close"],
        "prev_close": ["PrvsClsgPric", "PREV_CLOSE", "Prev Close"],
        "volume": ["TtlTradgVol", "TOTTRDQTY", "Total Traded Quantity"],
        "value": ["TtlTrfVal", "TOTTRDVAL", "Total Traded Value"],
        "trades": ["TtlNbOfTxsExctd", "TOTALTRADES", "Total Trades"],
        "delivery_qty": ["DlvryQty", "DELIV_QTY", "Delivery Quantity"],
        "delivery_pct": ["DlvryPct", "DELIV_PER", "Delivery %"],
        "vwap": ["VWAP", "WghtdAvrgPric"],
        "date": ["TradDt", "TIMESTAMP", "Trade Date"],
    }
    selected = {}
    for target, names in aliases.items():
        col = _first(df, names)
        if col:
            selected[target] = df[col]
    if "symbol" not in selected:
        raise RuntimeError(f"Cannot identify symbol in bhavcopy. Columns={list(df.columns)}")
    out = pd.DataFrame(selected)
    numeric = ["open","high","low","close","prev_close","volume","value","trades",
               "delivery_qty","delivery_pct","vwap"]
    for c in numeric:
        if c in out:
            out[c] = pd.to_numeric(
                out[c].astype(str).str.replace(",", "", regex=False).replace({"-": None, "": None}),
                errors="coerce"
            )
    out["symbol"] = out["symbol"].astype(str).str.strip()
    if "series" in out:
        out["series"] = out["series"].astype(str).str.strip()
    return out
