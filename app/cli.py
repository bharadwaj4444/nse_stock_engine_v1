from __future__ import annotations

import argparse
from datetime import date
from dateutil.relativedelta import relativedelta

from app.ingest import download_universe
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

    args = p.parse_args()

    if args.cmd == "universe":
        print(f"Universe rows written: {download_universe()}")

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
