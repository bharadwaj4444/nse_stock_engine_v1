from __future__ import annotations

import argparse
from datetime import date
from dateutil.relativedelta import relativedelta
from app.ttm import build_ttm_for_all, build_ttm_for_company
from app.ratios import build_ratios_for_all
from app.verification_history import get_verification_history

from app.ingest import (
    download_universe,
    ingest_financial_filings,
    ingest_financial_filings_for_universe,
    process_cached_financial_filings,
)
from app.indicators import calculate_for_date
from app.market import build_market_metrics_for_company
from app.valuation import build_valuations_for_all_companies
from app.historical_features import build_historical_features
from app.feature_scores import build_feature_scores
from app.stock_rankings import build_stock_rankings
from app.db import engine
from sqlalchemy import text
from app.pipeline import backfill, daily
from app.verification import print_report

def main():
    p = argparse.ArgumentParser(description="NSE Stock Engine V1")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("universe")

    b = sub.add_parser("backfill")
    b.add_argument("--years", type=int, default=5)
    b.add_argument("--start")
    b.add_argument("--end")
    b.add_argument(
        "--force",
        action="store_true",
        help="Re-download and reprocess every requested date",
    )

    i = sub.add_parser("indicators")
    i.add_argument("--date")

    sub.add_parser("daily")

    analyze = sub.add_parser("analyze")
    analyze.add_argument("--date", required=True, help="Trading date in YYYY-MM-DD format")

    verify = sub.add_parser("verify")
    verify.add_argument(
        "--date",
        required=True,
        help="Trading date in YYYY-MM-DD format",
    )

    history = sub.add_parser(
        "verification-history",
        help="Show recent verification runs",
    )
    history.add_argument(
        "--date",
        help="Filter by trade date (YYYY-MM-DD)",
    )
    history.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Maximum number of runs to display (default: 20)",
    )

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
        rebuild_ttm(args.symbol)

    elif args.cmd == "financial-process":
        written = process_cached_financial_filings(
            symbol=args.symbol,
        )
        print(
            f"Financial statements written: {written}"
        )
        rebuild_ttm(args.symbol)
        
    elif args.cmd == "backfill":
        if args.start:
            start = date.fromisoformat(args.start)
        else:
            start = date.today() - relativedelta(years=args.years)
        end = date.fromisoformat(args.end) if args.end else date.today()
        backfill(
            start,
            end,
            force=args.force,
        )

    elif args.cmd == "indicators":
        calculate_for_date(date.fromisoformat(args.date) if args.date else None)

    elif args.cmd == "daily":
        daily()

    elif args.cmd == "analyze":
        target_date = date.fromisoformat(args.date)

        with engine.connect() as conn:
            price_count = conn.execute(
                text("SELECT COUNT(*) FROM daily_prices WHERE trade_date = :d"),
                {"d": target_date},
            ).scalar_one()

            company_ids = conn.execute(
                text("SELECT id FROM companies WHERE is_active = TRUE ORDER BY id")
            ).scalars().all()

        if price_count == 0:
            raise RuntimeError(f"No daily_prices rows found for {target_date}")

        print(f"Analyze date: {target_date}")
        print(f"Daily price rows available: {price_count}")
        print(f"Active companies: {len(company_ids)}")

        market_rows = 0
        for index, company_id in enumerate(company_ids, start=1):
            market_rows += build_market_metrics_for_company(
                company_id, target_date, target_date
            )
            if index % 250 == 0:
                print(f"Market metrics progress: {index}/{len(company_ids)}")

        print(f"Market metric rows written: {market_rows}")

        ratio_rows = build_ratios_for_all()
        print(f"Financial ratio rows upserted: {ratio_rows}")

        companies_valued, valuation_rows = build_valuations_for_all_companies(
            target_date, target_date
        )
        print(
            f"Valuations: companies processed={companies_valued}, "
            f"rows written={valuation_rows}"
        )

        feature_rows = build_historical_features(target_date, target_date)
        print(f"Historical feature rows: {feature_rows}")

        score_rows = build_feature_scores(target_date, target_date)
        print(f"Feature score rows written: {score_rows}")

        ranking_rows = build_stock_rankings(target_date, target_date)
        print(f"Stock ranking rows written: {ranking_rows}")

        print()
        print("Running post-analysis verification...")

        success = print_report(target_date, trigger="analyze")

        if not success:
            raise SystemExit(1)

    elif args.cmd == "verify":
        target_date = date.fromisoformat(args.date)
        success = print_report(target_date, trigger="verify")

        if not success:
            raise SystemExit(1)

    elif args.cmd == "verification-history":
        target_date = (
            date.fromisoformat(args.date)
            if args.date
            else None
        )

        runs = get_verification_history(
            target_date=target_date,
            limit=args.limit,
        )

        if not runs:
            print("No verification history found.")
        else:
            print("\nVerification History")
            print("-" * 105)
            print(
                f"{'Run ID':<8} "
                f"{'Trade Date':<12} "
                f"{'Trigger':<10} "
                f"{'Completed At':<30} "
                f"{'Checks':>7} "
                f"{'Failures':>9} "
                f"{'Warnings':>9}"
            )
            print("-" * 105)

            for run in runs:
                print(
                    f"{run.id:<8} "
                    f"{run.trade_date!s:<12} "
                    f"{run.trigger:<10} "
                    f"{run.completed_at:%Y-%m-%d %H:%M:%S %z} "
                    f"{run.check_count:>7} "
                    f"{run.failure_count:>9} "
                    f"{run.warning_count:>9}"
                )

            print("-" * 105)
            print(f"Total runs displayed: {len(runs)}")

def rebuild_ttm(symbol: str | None = None) -> int:
    """Rebuild TTM data for one company or the complete universe."""
    if not symbol:
        written = build_ttm_for_all()
        print(f"TTM rows inserted or updated: {written}")
        return written

    with engine.connect() as conn:
        company_id = conn.execute(
            text("""
                SELECT id
                FROM companies
                WHERE UPPER(nse_symbol) = UPPER(:symbol)
            """),
            {"symbol": symbol.strip()},
        ).scalar_one_or_none()

        if company_id is None:
            raise ValueError(f"Company not found for symbol: {symbol}")

        scopes = conn.execute(
            text("""
                SELECT DISTINCT statement_scope
                FROM financial_statements_canonical
                WHERE company_id = :company_id
                  AND period_type = 'quarterly'
                ORDER BY statement_scope
            """),
            {"company_id": company_id},
        ).scalars().all()

    written = sum(
        build_ttm_for_company(int(company_id), scope)
        for scope in scopes
    )

    print(
        f"TTM rebuilt for {symbol.upper()}: "
        f"scopes={len(scopes)}, rows inserted or updated={written}"
    )
    return written

if __name__ == "__main__":
    main()
