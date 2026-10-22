
import argparse
import csv
from pathlib import Path

import pandas as pd

from app.db import SessionLocal
from app.indicators import calculate
from app.models import BenchmarkPrice, Company, DailyPrice, TechnicalIndicator


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol", default="RELIANCE")
    parser.add_argument(
        "--output",
        default="data/validation/RELIANCE_nifty_relative.csv",
    )
    args = parser.parse_args()

    symbol = args.symbol.upper()

    with SessionLocal() as db:
        company = (
            db.query(Company)
            .filter(Company.nse_symbol == symbol)
            .one()
        )

        prices = (
            db.query(DailyPrice)
            .filter(DailyPrice.company_id == company.id)
            .order_by(DailyPrice.trade_date)
            .all()
        )

        benchmarks = (
            db.query(BenchmarkPrice)
            .filter(
                BenchmarkPrice.benchmark == "NIFTY50",
                BenchmarkPrice.close_price.isnot(None),
            )
            .order_by(BenchmarkPrice.trade_date)
            .all()
        )

        stored_rows = (
            db.query(TechnicalIndicator)
            .filter(TechnicalIndicator.company_id == company.id)
            .all()
        )

        stored_by_date = {
            row.trade_date: row for row in stored_rows
        }

        stock_df = pd.DataFrame(
            [
                {
                    "trade_date": pd.Timestamp(p.trade_date),
                    "open": float(p.open_price),
                    "high": float(p.high_price),
                    "low": float(p.low_price),
                    "close": float(p.close_price),
                    "volume": float(p.volume or 0),
                }
                for p in prices
                if p.close_price is not None
            ]
        )

        nifty = pd.Series(
            {
                pd.Timestamp(row.trade_date): float(row.close_price)
                for row in benchmarks
            },
            dtype=float,
        ).sort_index()

        if stock_df.empty or nifty.empty:
            raise RuntimeError("Stock or NIFTY price history is empty.")

        result = calculate(stock_df, nifty=nifty)

        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with output_path.open("w", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            writer.writerow([
                "trade_date",
                "stock_close",
                "nifty_close",
                "python_relative_20d",
                "db_relative_20d",
                "python_relative_60d",
                "db_relative_60d",
            ])

            nifty_by_date = {
                timestamp.date(): close
                for timestamp, close in nifty.items()
            }

            for i, row in result.iterrows():
                trade_date = pd.Timestamp(row["trade_date"]).date()
                stored = stored_by_date.get(trade_date)

                writer.writerow([
                    trade_date.isoformat(),
                    stock_df.iloc[i]["close"],
                    nifty_by_date.get(trade_date),
                    row.get("nifty_relative_20d"),
                    getattr(stored, "nifty_relative_20d", None),
                    row.get("nifty_relative_60d"),
                    getattr(stored, "nifty_relative_60d", None),
                ])

    print(f"Symbol: {symbol}")
    print(f"Stock rows: {len(stock_df)}")
    print(f"NIFTY rows: {len(nifty)}")
    print(f"Output: {output_path.resolve()}")


if __name__ == "__main__":
    main()