from __future__ import annotations

import argparse
import json
import time
from datetime import date
from pathlib import Path

import pandas as pd
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.db import SessionLocal
from app.indicators import calculate
from app.models import BenchmarkPrice, Company, DailyPrice, TechnicalIndicator


# Keep aligned with app/indicators.py and TechnicalIndicator.
INDICATOR_FIELDS = [
    "sma20", "sma50", "sma100", "sma200",
    "ema20", "ema50", "rsi14",
    "macd", "macd_signal", "macd_histogram",
    "atr14", "bb_upper", "bb_middle", "bb_lower",
    "adx14", "volatility20", "volatility60",
    "return_1d", "return_5d", "return_20d",
    "return_60d", "return_120d", "return_252d",
    "relative_volume20", "nifty_relative_20d", "nifty_relative_60d",
]

LOOKBACK_ROWS = 550
UPSERT_BATCH_SIZE = 400
CHECKPOINT_PATH = (
    Path(__file__).resolve().parent / "historical_indicator_rebuild_checkpoint.json"
)


def db_value(value):
    """Convert pandas/NumPy values into PostgreSQL-safe Python values."""
    if value is None or pd.isna(value):
        return None
    return float(value)


def load_target_dates(db) -> list[date]:
    # Use all downloaded price dates, including dates that may only have
    # prices for companies which are currently inactive.
    return list(
        db.scalars(
            select(DailyPrice.trade_date)
            .distinct()
            .order_by(DailyPrice.trade_date)
        ).all()
    )


def load_prices_by_active_company(db) -> dict[int, pd.DataFrame]:
    """
    Read active-company prices in one query, rather than querying once per
    company and target date. Only the columns needed by calculate() are read.
    """
    stmt = (
        select(
            DailyPrice.company_id,
            DailyPrice.trade_date,
            DailyPrice.open_price,
            DailyPrice.high_price,
            DailyPrice.low_price,
            DailyPrice.close_price,
            DailyPrice.volume,
        )
        .join(Company, Company.id == DailyPrice.company_id)
        .where(Company.is_active.is_(True))
        .order_by(DailyPrice.company_id, DailyPrice.trade_date)
    )

    frame = pd.read_sql_query(stmt, db.connection())
    if frame.empty:
        return {}

    frame["trade_date"] = pd.to_datetime(frame["trade_date"])
    for column in (
        "open_price", "high_price", "low_price", "close_price", "volume"
    ):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame["volume"] = frame["volume"].fillna(0)

    # Grouping copies the individual company frames. The full frame is deleted
    # immediately afterward to keep memory use bounded.
    groups = {
        int(company_id): group.reset_index(drop=True)
        for company_id, group in frame.groupby("company_id", sort=False)
    }
    del frame
    return groups


def load_benchmark_series(db) -> pd.Series | None:
    rows = db.execute(
        select(BenchmarkPrice.trade_date, BenchmarkPrice.close_price)
        .where(
            BenchmarkPrice.benchmark == "NIFTY50",
            BenchmarkPrice.close_price.is_not(None),
        )
        .order_by(BenchmarkPrice.trade_date)
    ).all()

    if not rows:
        return None

    index = pd.DatetimeIndex([pd.Timestamp(row.trade_date) for row in rows])
    values = [float(row.close_price) for row in rows]
    return pd.Series(values, index=index).sort_index()


def load_checkpoint_state(db, checkpoint_date: date, price_groups):
    """
    Restore each company's latest stored indicator values at the checkpoint
    date and advance its price cursor beyond that date.
    """
    checkpoint_ts = pd.Timestamp(checkpoint_date)
    expected_company_ids = {
        company_id
        for company_id, prices in price_groups.items()
        if prices["trade_date"].iloc[0] <= checkpoint_ts
    }

    rows = db.scalars(
        select(TechnicalIndicator).where(
            TechnicalIndicator.trade_date == checkpoint_date
        )
    ).all()
    rows_by_company = {row.company_id: row for row in rows}

    if set(rows_by_company) != expected_company_ids:
        raise RuntimeError(
            "Checkpoint date is not complete in technical_indicators. "
            f"Date={checkpoint_date}; expected rows={len(expected_company_ids)}; "
            f"stored rows={len(rows_by_company)}. Do not resume from this "
            "checkpoint; inspect the database or restart the rebuild."
        )

    latest_values = {
        company_id: {
            field: db_value(getattr(row, field))
            for field in INDICATOR_FIELDS
        }
        for company_id, row in rows_by_company.items()
    }

    next_index = {
        company_id: int(
            prices["trade_date"].searchsorted(checkpoint_ts, side="right")
        )
        for company_id, prices in price_groups.items()
    }
    return latest_values, next_index


def save_checkpoint(target: date) -> None:
    CHECKPOINT_PATH.parent.mkdir(parents=True, exist_ok=True)
    temp_path = CHECKPOINT_PATH.with_suffix(".tmp")
    temp_path.write_text(
        json.dumps({"last_completed_date": target.isoformat()}, indent=2),
        encoding="utf-8",
    )
    temp_path.replace(CHECKPOINT_PATH)


def upsert_date(db, payload: list[dict]) -> None:
    if payload:
        stmt = insert(TechnicalIndicator)
        update_fields = {
            field: getattr(stmt.excluded, field)
            for field in INDICATOR_FIELDS
        }
        stmt = stmt.on_conflict_do_update(
            index_elements=[
                TechnicalIndicator.company_id,
                TechnicalIndicator.trade_date,
            ],
            set_=update_fields,
        )

        for start in range(0, len(payload), UPSERT_BATCH_SIZE):
            db.execute(stmt, payload[start:start + UPSERT_BATCH_SIZE])

    # Commit even on dates with no active-company rows so each target date has
    # a clear transaction boundary.
    db.commit()


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Rebuild historical technical indicators from existing daily_prices "
            "without downloading data or changing the production pipeline."
        )
    )
    parser.add_argument(
        "--end-date",
        type=date.fromisoformat,
        help="Optional inclusive end date (YYYY-MM-DD); defaults to latest price date.",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume after the last date in the local checkpoint file.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Calculate and report progress without writing rows or checkpoints.",
    )
    args = parser.parse_args()

    if args.resume and args.dry_run:
        parser.error("--resume and --dry-run cannot be combined.")

    with SessionLocal() as db:
        try:
            all_dates = load_target_dates(db)
            if not all_dates:
                raise RuntimeError("daily_prices contains no dates.")

            end_date = args.end_date or all_dates[-1]
            target_dates = [d for d in all_dates if d <= end_date]
            if not target_dates:
                raise RuntimeError(
                    f"No daily_prices dates exist on or before {end_date}."
                )

            print(
                f"Downloaded dates: {len(all_dates)}; "
                f"range={all_dates[0]}..{all_dates[-1]}"
            )
            print(
                f"Dates selected for this run: {len(target_dates)}; "
                f"end_date={end_date}"
            )

            price_groups = load_prices_by_active_company(db)
            if not price_groups:
                raise RuntimeError("No price history found for active companies.")

            total_price_rows = sum(len(frame) for frame in price_groups.values())
            print(
                f"Loaded {total_price_rows:,} active-company price rows "
                f"across {len(price_groups):,} companies."
            )

            nifty_all = load_benchmark_series(db)
            if nifty_all is None:
                print("WARNING: no NIFTY50 benchmark rows found.")
            else:
                print(
                    f"Loaded {len(nifty_all):,} NIFTY50 rows; "
                    f"range={nifty_all.index.min().date()}.."
                    f"{nifty_all.index.max().date()}"
                )

            latest_values: dict[int, dict] = {}
            next_index = {company_id: 0 for company_id in price_groups}
            first_target_index = 0

            if args.resume:
                if not CHECKPOINT_PATH.exists():
                    raise RuntimeError(
                        f"No checkpoint found at {CHECKPOINT_PATH}. "
                        "Run without --resume to start from the earliest date."
                    )

                checkpoint = json.loads(
                    CHECKPOINT_PATH.read_text(encoding="utf-8")
                )
                checkpoint_date = date.fromisoformat(
                    checkpoint["last_completed_date"]
                )
                if checkpoint_date not in all_dates:
                    raise RuntimeError(
                        f"Checkpoint date {checkpoint_date} is not present "
                        "in daily_prices. Check the checkpoint before continuing."
                    )

                latest_values, next_index = load_checkpoint_state(
                    db, checkpoint_date, price_groups
                )
                first_target_index = next(
                    (
                        i + 1 for i, d in enumerate(target_dates)
                        if d == checkpoint_date
                    ),
                    0,
                )
                if first_target_index == 0:
                    raise RuntimeError(
                        f"Checkpoint date {checkpoint_date} is after the "
                        f"requested end date {end_date} or not in the selected range."
                    )

                print(
                    f"Resuming after {checkpoint_date}; "
                    f"restored {len(latest_values):,} company indicator states."
                )

            elif not args.dry_run:
                print(
                    "Starting from the earliest downloaded date. "
                    "Existing rows will be safely upserted."
                )

            started = time.perf_counter()
            dates_to_process = target_dates[first_target_index:]

            for offset, target in enumerate(dates_to_process, start=1):
                target_ts = pd.Timestamp(target)
                nifty = None
                if nifty_all is not None:
                    nifty = nifty_all.loc[:target_ts]
                    if nifty.empty:
                        nifty = None

                recalculated = 0

                # Only recalculate a company when it has a price on this date.
                # For dates without a new price, the existing calculate_date()
                # logic returns the same last-price-row indicators, so the
                # latest values are carried forward to this target date.
                for company_id, prices in price_groups.items():
                    idx = next_index[company_id]
                    if idx >= len(prices):
                        continue
                    if prices.at[idx, "trade_date"] != target_ts:
                        continue

                    start = max(0, idx + 1 - LOOKBACK_ROWS)
                    window = prices.iloc[start:idx + 1]
                    df = window[
                        [
                            "trade_date", "open_price", "high_price",
                            "low_price", "close_price", "volume",
                        ]
                    ].rename(
                        columns={
                            "open_price": "open",
                            "high_price": "high",
                            "low_price": "low",
                            "close_price": "close",
                        }
                    ).copy()

                    result = calculate(df, nifty=nifty)
                    row = result.iloc[-1]
                    latest_values[company_id] = {
                        field: db_value(row.get(field))
                        for field in INDICATOR_FIELDS
                    }
                    next_index[company_id] = idx + 1
                    recalculated += 1

                payload = [
                    {
                        "company_id": company_id,
                        "trade_date": target,
                        **values,
                    }
                    for company_id, values in latest_values.items()
                ]

                if args.dry_run:
                    # Do not commit or create a checkpoint in dry-run mode.
                    db.rollback()
                else:
                    upsert_date(db, payload)
                    save_checkpoint(target)

                elapsed = time.perf_counter() - started
                print(
                    f"[{first_target_index + offset}/{len(target_dates)}] "
                    f"{target}: recalculated={recalculated:,}, "
                    f"rows_for_date={len(payload):,}, "
                    f"elapsed={elapsed / 60:.1f} min"
                    + (" (DRY RUN)" if args.dry_run else "")
                )

            print(
                "\nRebuild run finished. "
                f"Dates processed={len(dates_to_process):,}; "
                f"elapsed={(time.perf_counter() - started) / 60:.1f} min."
            )
            if args.dry_run:
                print("DRY RUN: database rows and checkpoint were not changed.")
            else:
                print(f"Checkpoint: {CHECKPOINT_PATH}")

        except Exception:
            db.rollback()
            raise


if __name__ == "__main__":
    main()
