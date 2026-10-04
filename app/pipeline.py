from datetime import date, timedelta

from app.ingest import download_universe, ingest_bhavcopy
from app.indicators import calculate_for_date
from app.sources.nse import NSEClient
from app.sources.nse_calendar import NSETradingCalendar


calendar = NSETradingCalendar()


def date_range(start, end):
    d = start

    while d <= end:
        if calendar.is_trading_day(d):
            yield d

        d += timedelta(days=1)


def backfill(
    start: date,
    end: date,
    *,
    force: bool = False,
):
    client = NSEClient()

    total = 0
    skipped = 0
    non_trading = 0
    failed = 0

    for d in date_range(start, end):
        try:
            n = ingest_bhavcopy(
                d,
                client,
                force=force,
            )

            if n == 0:
                skipped += 1
            else:
                total += n

            print(
                f"{d}: {n} rows"
            )

        except Exception as exc:
            failed += 1

            print(
                f"{d}: failed: {exc}"
            )

    # Count non-trading dates separately.
    d = start
    while d <= end:
        if not calendar.is_trading_day(d):
            non_trading += 1

        d += timedelta(days=1)

    print()
    print(
        f"Backfill complete: "
        f"{total} rows written"
    )
    print(
        f"Dates skipped: "
        f"{skipped}"
    )
    print(
        f"Dates non-trading: "
        f"{non_trading}"
    )
    print(
        f"Dates failed: "
        f"{failed}"
    )


def daily():
    print("Refreshing NSE universe...")
    download_universe()

    client = NSEClient()
    d = date.today()

    # Walk backwards until the most recent NSE trading day.
    for _ in range(7):
        if not calendar.is_trading_day(d):
            print(
                f"{d}: {calendar.classify(d)}"
            )
            d -= timedelta(days=1)
            continue

        try:
            n = ingest_bhavcopy(
                d,
                client,
            )

            print(
                f"Latest bhavcopy: "
                f"{d} ({n} rows)"
            )

            calculate_for_date(d)

            print(
                f"Indicators calculated: "
                f"{d}"
            )

            return

        except Exception as exc:
            print(
                f"{d}: not available yet: "
                f"{exc}"
            )

            d -= timedelta(days=1)

    raise RuntimeError(
        "Could not find a recent NSE bhavcopy "
        "within 7 days"
    )