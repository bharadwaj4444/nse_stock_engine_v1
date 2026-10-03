from __future__ import annotations

import argparse
from datetime import date
from dateutil.relativedelta import relativedelta

from app.ingest import (
    download_universe,
    ingest_financial_filings,
    ingest_financial_filings_for_universe,
    process_cached_financial_filings,
)
from app.indicators import calculate_for_date
from app.pipeline import backfill, daily

def main():
    p = argparse.ArgumentParser(description="NSE Stock Engine V1")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("universe")

    b = sub.add_parser("backfill")
    b.add_argument("--years", type=int, default=5)
    b.add_argument("--start")
    b.add_argument("--end")

    i = sub.add_parser("indicators")
    i.add_argument("--date")

    sub.add_parser("daily")

    fd = sub.add_parser("financial-download")
    fd.add_argument("--symbol")
    fd.add_argument("--from-date", default="01-01-2025")
    fd.add_argument("--to-date")
    fd.add_argument("--delay", type=float, default=1.0)

    fp = sub.add_parser("financial-process")
    fp.add_argument("--symbol")

    args = p.parse_args()

    if args.cmd == "universe":
        print(f"Universe rows written: {download_universe()}")
    
    elif args.cmd == "financial-download":
        if args.symbol:
            written = ingest_financial_filings(
                symbol=args.symbol,
                from_date=args.from_date,
                to_date=args.to_date,
            )
            print(
                f"Financial statements written: {written}"
            )
        else:
            written = ingest_financial_filings_for_universe(
                from_date=args.from_date,
                to_date=args.to_date,
                delay_seconds=args.delay,
            )
            print(
                f"Financial statements written: {written}"
            )

    elif args.cmd == "financial-process":
        written = process_cached_financial_filings(
            symbol=args.symbol,
        )
        print(
            f"Financial statements written: {written}"
        )
        
    elif args.cmd == "backfill":
        if args.start:
            start = date.fromisoformat(args.start)
        else:
            start = date.today() - relativedelta(years=args.years)
        end = date.fromisoformat(args.end) if args.end else date.today()
        backfill(start, end)

    elif args.cmd == "indicators":
        calculate_for_date(date.fromisoformat(args.date) if args.date else None)

    elif args.cmd == "daily":
        daily()

if __name__ == "__main__":
    main()
