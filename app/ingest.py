from __future__ import annotations

import hashlib
from datetime import date, datetime
from pathlib import Path

import pandas as pd
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.config import settings
from app.db import SessionLocal
from app.models import Company, DailyPrice, FinancialStatement, IngestionRun
from app.sources.nse import NSEClient
from app.sources.nse_financials import NSEFinancialClient

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

def save_financial_statements(rows: list[dict]) -> int:
    if not rows:
        return 0

    written = 0

    with SessionLocal.begin() as db:
        for row in rows:
            company_id = row["company_id"]

            stmt = insert(FinancialStatement).values(
                company_id=company_id,
                period_type=row["period_type"],
                period_end=row["period_end"],
                filing_date=row.get("filing_date"),
                revenue=row.get("revenue"),
                ebitda=row.get("ebitda"),
                ebit=row.get("ebit"),
                profit_before_tax=row.get("profit_before_tax"),
                net_income=row.get("net_income"),
                eps=row.get("eps"),
                total_assets=row.get("total_assets"),
                total_equity=row.get("total_equity"),
                total_debt=row.get("total_debt"),
                cash_and_equivalents=row.get("cash_and_equivalents"),
                operating_cash_flow=row.get("operating_cash_flow"),
                capital_expenditure=row.get("capital_expenditure"),
                free_cash_flow=row.get("free_cash_flow"),
                source=row["source"],
                source_reference=row.get("source_reference"),
                statement_scope=row.get("statement_scope", "UNKNOWN"),
                submission_type=row.get("submission_type", "ORIGINAL"),
                audit_status=row.get("audit_status"),
                reporting_standard=row.get("reporting_standard"),
                source_url=row.get("source_url"),
            )

            stmt = stmt.on_conflict_do_update(
                constraint="uq_financial_statement_identity",
                set_={
                    "filing_date": stmt.excluded.filing_date,
                    "revenue": stmt.excluded.revenue,
                    "ebitda": stmt.excluded.ebitda,
                    "ebit": stmt.excluded.ebit,
                    "profit_before_tax": stmt.excluded.profit_before_tax,
                    "net_income": stmt.excluded.net_income,
                    "eps": stmt.excluded.eps,
                    "total_assets": stmt.excluded.total_assets,
                    "total_equity": stmt.excluded.total_equity,
                    "total_debt": stmt.excluded.total_debt,
                    "cash_and_equivalents": stmt.excluded.cash_and_equivalents,
                    "operating_cash_flow": stmt.excluded.operating_cash_flow,
                    "capital_expenditure": stmt.excluded.capital_expenditure,
                    "free_cash_flow": stmt.excluded.free_cash_flow,
                    "source_reference": stmt.excluded.source_reference,
                    "updated_at": datetime.now().astimezone(),
                    "statement_scope": stmt.excluded.statement_scope,
                    "submission_type": stmt.excluded.submission_type,
                    "audit_status": stmt.excluded.audit_status,
                    "reporting_standard": stmt.excluded.reporting_standard,
                    "source_url": stmt.excluded.source_url,
                },
            )

            db.execute(stmt)
            written += 1

    return written

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

def ingest_financial_filings(
    symbol: str,
    from_date: str = "01-01-2026",
    to_date: str | None = None,
) -> int:
    symbol = symbol.upper()

    client = NSEFinancialClient()

    # Resolve NSE symbol to the existing Company record.
    with SessionLocal() as db:
        company = db.execute(
            select(Company).where(
                Company.nse_symbol == symbol
            )
        ).scalar_one_or_none()

        if company is None:
            raise ValueError(
                f"Company not found for NSE symbol: {symbol}. "
                "Run universe ingestion first."
            )

        company_id = company.id

    filings = client.get_filings(
        symbol=symbol,
        from_date=from_date,
        to_date=to_date,
    )

    total_statements = 0

    for filing in filings:
        if not filing.xbrl_url:
            continue

        try:
            xml_text = client.download_xbrl(
                filing.xbrl_url
            )

            statements = client.parse_xbrl(
                xml_text=xml_text,
                filing=filing,
            )

            if not statements:
                continue

            # Attach the existing Company ID to every parsed statement.
            for statement in statements:
                statement["company_id"] = company_id

            saved = save_financial_statements(statements)
            total_statements += saved

        except Exception as exc:
            print(
                f"Financial filing failed: "
                f"{symbol} "
                f"{filing.period_end} "
                f"{filing.source_reference}: "
                f"{exc}"
            )

    return total_statements

def _int(v):
    try:
        if pd.isna(v):
            return None
        return int(float(v))
    except Exception:
        return None
