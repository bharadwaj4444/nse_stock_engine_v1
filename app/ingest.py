from __future__ import annotations

import hashlib
from datetime import date, datetime
from pathlib import Path

import pandas as pd
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.config import settings
from app.db import SessionLocal
from app.models import Company, DailyPrice, IngestionRun
from app.sources.nse import NSEClient

def save_universe(df: pd.DataFrame) -> int:
    written = 0
    with SessionLocal.begin() as db:
        existing = {x.nse_symbol: x for x in db.scalars(select(Company)).all()}
        for row in df.itertuples(index=False):
            symbol = row.nse_symbol
            if symbol in existing:
                c = existing[symbol]
                c.isin = row.isin if pd.notna(row.isin) else c.isin
                c.company_name = row.company_name
                c.series = row.series if pd.notna(row.series) else c.series
                c.listing_date = row.listing_date if pd.notna(row.listing_date) else c.listing_date
                c.is_active = True
                c.updated_at = datetime.now().astimezone()
            else:
                db.add(Company(
                    nse_symbol=symbol,
                    isin=row.isin if pd.notna(row.isin) else None,
                    company_name=row.company_name,
                    series=row.series if pd.notna(row.series) else None,
                    listing_date=row.listing_date if pd.notna(row.listing_date) else None,
                    is_active=True,
                    source_updated_at=datetime.now().astimezone(),
                ))
            written += 1
    return written

def download_universe() -> int:
    client = NSEClient()
    df = client.universe()
    return save_universe(df)

def _company_map(db):
    return {c.nse_symbol: c.id for c in db.scalars(select(Company)).all()}

def ingest_bhavcopy(trade_date: date, client: NSEClient | None = None) -> int:
    client = client or NSEClient()
    started = datetime.now().astimezone()
    raw_dir = Path(settings.raw_data_dir) / "nse" / "cm" / trade_date.strftime("%Y/%m/%d")
    raw_dir.mkdir(parents=True, exist_ok=True)

    with SessionLocal.begin() as db:
        run = IngestionRun(
            run_type="bhavcopy",
            trade_date=trade_date,
            source="NSE",
            status="RUNNING",
            started_at=started,
        )
        db.add(run)
        db.flush()
        run_id = run.id

    try:
        df, url, content = client.bhavcopy(trade_date)
        digest = hashlib.sha256(content).hexdigest()
        zip_path = raw_dir / f"BhavCopy_{trade_date:%Y%m%d}.csv.zip"
        zip_path.write_bytes(content)

        # Only normal equity series are used for the initial V1 universe.
        if "series" in df.columns:
            df = df[df["series"].isin(["EQ", "BE", "BZ", "SM", "ST"])].copy()

        with SessionLocal.begin() as db:
            cmap = _company_map(db)
            rows = []
            for r in df.itertuples(index=False):
                company_id = cmap.get(r.symbol)
                if not company_id:
                    continue
                rows.append({
                    "company_id": company_id,
                    "trade_date": trade_date,
                    "open_price": getattr(r, "open", None),
                    "high_price": getattr(r, "high", None),
                    "low_price": getattr(r, "low", None),
                    "close_price": getattr(r, "close", None),
                    "prev_close": getattr(r, "prev_close", None),
                    "volume": _int(getattr(r, "volume", None)),
                    "traded_value": getattr(r, "value", None),
                    "trades_count": _int(getattr(r, "trades", None)),
                    "delivery_qty": _int(getattr(r, "delivery_qty", None)),
                    "delivery_pct": getattr(r, "delivery_pct", None),
                    "vwap": getattr(r, "vwap", None),
                    "source_file": f"{url} sha256={digest}",
                })
            if rows:
                stmt = insert(DailyPrice).values(rows)
                stmt = stmt.on_conflict_do_update(
                    index_elements=["company_id", "trade_date"],
                    set_={k: getattr(stmt.excluded, k) for k in [
                        "open_price","high_price","low_price","close_price","prev_close",
                        "volume","traded_value","trades_count","delivery_qty","delivery_pct",
                        "vwap","source_file"
                    ]}
                )
                db.execute(stmt)
            run = db.get(IngestionRun, run_id)
            run.status = "SUCCESS"
            run.records_seen = len(df)
            run.records_written = len(rows)
            run.finished_at = datetime.now().astimezone()
            return len(rows)
    except Exception as exc:
        with SessionLocal.begin() as db:
            run = db.get(IngestionRun, run_id)
            if run:
                run.status = "FAILED"
                run.error_message = repr(exc)
                run.finished_at = datetime.now().astimezone()
        raise

def _int(v):
    try:
        if pd.isna(v):
            return None
        return int(float(v))
    except Exception:
        return None
