from datetime import date, timedelta
from app.ingest import download_universe, ingest_bhavcopy
from app.indicators import calculate_for_date
from app.sources.nse import NSEClient

def date_range(start, end):
    d = start
    while d <= end:
        if d.weekday() < 5:
            yield d
        d += timedelta(days=1)

def backfill(start: date, end: date):
    client = NSEClient()
    total = 0
    for d in date_range(start, end):
        try:
            n = ingest_bhavcopy(d, client)
            print(f"{d}: {n} rows")
            total += n
        except Exception as exc:
            # 404/non-trading dates are normal; other failures are reported and processing continues.
            print(f"{d}: skipped/failed: {exc}")
    print(f"Backfill complete: {total} rows written")

def daily():
    print("Refreshing NSE universe...")
    download_universe()
    client = NSEClient()
    d = date.today()
    # Try today, then walk back to the most recent available report.
    for _ in range(7):
        try:
            n = ingest_bhavcopy(d, client)
            print(f"Latest bhavcopy: {d} ({n} rows)")
            calculate_for_date(d)
            print(f"Indicators calculated: {d}")
            return
        except Exception as exc:
            print(f"{d}: not available yet: {exc}")
            d -= timedelta(days=1)
    raise RuntimeError("Could not find a recent NSE bhavcopy within 7 days")
