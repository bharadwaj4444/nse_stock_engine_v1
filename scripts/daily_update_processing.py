
import argparse
import subprocess
import sys
from pathlib import Path
from datetime import date

from sqlalchemy import func, select

# Run from the repository root.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.db import SessionLocal
from app.models import DailyPrice


def get_dates(start_date, end_date):
    with SessionLocal() as db:
        dates = db.execute(
            select(DailyPrice.trade_date)
            .where(
                DailyPrice.trade_date >= start_date,
                DailyPrice.trade_date <= end_date,
            )
            .distinct()
            .order_by(DailyPrice.trade_date)
        ).scalars().all()

        latest_date = db.execute(
            select(func.max(DailyPrice.trade_date))
        ).scalar_one()

    return dates, latest_date


def run_cli(*args):
    command = [sys.executable, "-m", "app.cli", *map(str, args)]
    print(f"\nRunning: {' '.join(command)}", flush=True)
    subprocess.run(command, cwd=ROOT, check=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    args = parser.parse_args()

    start_date = date.fromisoformat(args.start)
    end_date = date.fromisoformat(args.end)

    dates, latest_date = get_dates(start_date, end_date)

    if not latest_date:
        raise RuntimeError("daily_prices is empty; cannot run analysis.")

    if not dates:
        print("No price dates found inside the recovery window.")

    print(f"Found {len(dates)} distinct trading dates to process.")

    for index, trade_date in enumerate(dates, start=1):
        print(
            f"\n[{index}/{len(dates)}] Calculating indicators for {trade_date}",
            flush=True,
        )
        run_cli("indicators", "--date", trade_date.isoformat())

    print(f"\nAnalyzing latest available price date: {latest_date}")
    run_cli("analyze", "--date", latest_date.isoformat())


if __name__ == "__main__":
    main()
