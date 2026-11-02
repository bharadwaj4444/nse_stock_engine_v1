from datetime import date, timedelta

from app.ingest import download_universe, ingest_bhavcopy
from app.indicators import calculate_for_date
from app.sources.nse import NSEClient
from app.sources.nse_calendar import NSETradingCalendar
from app.adapters.outbound.backtest import BacktestAdapter
from app.adapters.outbound.market_data import MarketDataAdapter
from app.adapters.outbound.news_source import NewsSignalSourceAdapter
from app.adapters.outbound.persistence import RecommendationPersistenceAdapter
from app.core.engine import run_closed_loop
from app.db import SessionLocal


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


def run_closed_loop_for_date(trade_date: date):
    """
    Run the closed-loop recommendation stages for one trading date.

    Stages: score -> hold -> verify -> refine -> override.
    """

    with SessionLocal() as session:
        ranking_store = RecommendationPersistenceAdapter(session)
        market_data = MarketDataAdapter(session)
        news_source = NewsSignalSourceAdapter(session)
        backtest = BacktestAdapter(session)

        result = run_closed_loop(
            trade_date,
            ranking_store=ranking_store,
            market_data=market_data,
            news_source=news_source,
            backtest=backtest,
        )

    return result


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

            loop_result = run_closed_loop_for_date(d)

            print(
                f"Closed-loop scoring complete: "
                f"{len(loop_result.scored)} instruments scored"
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