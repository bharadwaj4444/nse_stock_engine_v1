from __future__ import annotations

import argparse
from datetime import date
from decimal import Decimal

import numpy as np
import pandas as pd
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.db import SessionLocal
from app.indicators import calculate
from app.models import (
    BenchmarkPrice,
    Company,
    DailyPrice,
    TechnicalIndicator,
)

# Keep this list aligned with app/indicators.py.
INDICATOR_FIELDS = [
    "sma20", "sma50", "sma100", "sma200",
    "ema20", "ema50", "rsi14",
    "macd", "macd_signal", "macd_histogram",
    "atr14", "bb_upper", "bb_middle", "bb_lower",
    "adx14", "volatility20", "volatility60",
    "return_1d", "return_5d", "return_20d",
    "return_60d", "return_120d", "return_252d",
    "relative_volume20",
    "nifty_relative_20d", "nifty_relative_60d",
]


def db_value(value):
    """Convert pandas/NumPy values into PostgreSQL-safe Python values."""
    if value is None or pd.isna(value):
        return None
    return float(value)


def calculate_date(db, target: date) -> list[dict]:
    benchmark_rows = db.execute(
        select(BenchmarkPrice.trade_date, BenchmarkPrice.close_price)
        .where(
            BenchmarkPrice.benchmark == "NIFTY50",
            BenchmarkPrice.trade_date <= target,
            BenchmarkPrice.close_price.is_not(None),
        )
        .order_by(BenchmarkPrice.trade_date)
    ).all()

    nifty = None
    if benchmark_rows:
        nifty = pd.Series(
            {
                pd.Timestamp(row.trade_date): float(row.close_price)
                for row in benchmark_rows
            }
        ).sort_index()

    companies = db.scalars(
        select(Company).where(Company.is_active.is_(True))
    ).all()

    payload = []

    for index, company in enumerate(companies, start=1):
        prices = db.scalars(
            select(DailyPrice)
            .where(
                DailyPrice.company_id == company.id,
                DailyPrice.trade_date <= target,
            )
            .order_by(DailyPrice.trade_date.desc())
            .limit(550)
        ).all()

        if not prices:
            continue

        prices.reverse()

        df = pd.DataFrame(
            [
                {
                    "trade_date": p.trade_date,
                    "open": float(p.open_price),
                    "high": float(p.high_price),
                    "low": float(p.low_price),
                    "close": float(p.close_price),
                    "volume": float(p.volume or 0),
                }
                for p in prices
            ]
        )
        df["trade_date"] = pd.to_datetime(df["trade_date"])
        df = df.sort_values("trade_date")

        result = calculate(df, nifty=nifty)
        row = result.iloc[-1]

        record = {
            "company_id": company.id,
            "trade_date": target,
        }
        for field in INDICATOR_FIELDS:
            record[field] = db_value(row.get(field))

        payload.append(record)

        if index % 250 == 0:
            print(
                f"Calculated {index}/{len(companies)} companies; "
                f"target={target}; rows={len(payload)}"
            )

    return payload


def compare_existing(db, target: date, payload: list[dict]) -> None:
    existing_rows = db.scalars(
        select(TechnicalIndicator).where(
            TechnicalIndicator.trade_date == target
        )
    ).all()

    existing_by_company = {
        row.company_id: row for row in existing_rows
    }

    common = 0
    missing = 0
    mismatches = 0
    max_diff = 0.0
    mismatch_examples = []

    # Database columns are Numeric(..., 6), so allow small rounding noise.
    tolerance = 0.000002

    for candidate in payload:
        old = existing_by_company.get(candidate["company_id"])
        if old is None:
            missing += 1
            continue

        common += 1

        for field in INDICATOR_FIELDS:
            expected = candidate[field]
            actual = getattr(old, field)

            # Treat None, NaN and database numeric NaN consistently.
            expected_missing = expected is None or bool(pd.isna(expected))
            actual_missing = actual is None or bool(pd.isna(actual))

            if expected_missing and actual_missing:
                continue

            if expected_missing != actual_missing:
                mismatches += 1
                if len(mismatch_examples) < 10:
                    mismatch_examples.append(
                        (candidate["company_id"], field, expected, actual)
                    )
                continue

            diff = abs(float(expected) - float(actual))
            max_diff = max(max_diff, diff)

            if diff > tolerance:
                mismatches += 1
                if len(mismatch_examples) < 10:
                    mismatch_examples.append(
                        (candidate["company_id"], field, expected, actual)
                    )

    print("\nValidation against existing database rows")
    print(f"Target date:             {target}")
    print(f"Calculated rows:         {len(payload)}")
    print(f"Existing rows:           {len(existing_rows)}")
    print(f"Rows compared:           {common}")
    print(f"New rows (not existing): {missing}")
    print(f"Field mismatches:        {mismatches}")
    print(f"Maximum numeric diff:     {max_diff:.10f}")

    if mismatch_examples:
        print("\nFirst mismatches:")
        for company_id, field, expected, actual in mismatch_examples:
            print(
                f"company_id={company_id}, {field}: "
                f"calculated={expected}, stored={actual}"
            )


def upsert_date(db, payload: list[dict]) -> None:
    if not payload:
        print("No indicator rows to write.")
        return

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

    # Keep each statement below PostgreSQL's parameter limit.
    batch_size = 400
    for start in range(0, len(payload), batch_size):
        batch = payload[start:start + batch_size]
        db.execute(stmt, batch)

    # A single date is one transaction. Failed writes roll back on close.
    db.commit()
    print(f"Upserted {len(payload)} rows.")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--date",
        required=True,
        type=date.fromisoformat,
        help="Target date in YYYY-MM-DD format",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Calculate and compare without writing to the database",
    )
    args = parser.parse_args()

    with SessionLocal() as db:
        try:
            print(f"Starting target date: {args.date}")
            payload = calculate_date(db, args.date)

            if args.dry_run:
                compare_existing(db, args.date, payload)
                print("\nDRY RUN: no database rows were changed.")
            else:
                upsert_date(db, payload)
        except Exception:
            db.rollback()
            raise


if __name__ == "__main__":
    main()


