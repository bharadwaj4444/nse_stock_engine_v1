from __future__ import annotations

from bisect import bisect_right
from datetime import date
from decimal import Decimal
from typing import Any

from requests import session
from sqlalchemy import text

from app.db import engine


def _calculate_market_cap(
    close_price: Decimal | None,
    shares_outstanding: Decimal | None,
) -> Decimal | None:
    if close_price is None or shares_outstanding is None:
        return None

    return close_price * shares_outstanding


def _load_prices(
    company_id: int | None = None,
) -> list[dict[str, Any]]:

    conditions = []
    params: dict[str, Any] = {}

    if company_id is not None:
        conditions.append("company_id = :company_id")
        params["company_id"] = company_id

    where = ""

    if conditions:
        where = "WHERE " + " AND ".join(conditions)

    sql = f"""
        SELECT
            company_id,
            trade_date,
            close_price,
            vwap,
            volume
        FROM daily_prices
        {where}
        ORDER BY company_id, trade_date
    """

    with engine.connect() as conn:
        rows = conn.execute(
            text(sql),
            params,
        ).mappings().all()

    return [dict(row) for row in rows]


def _load_share_data(
    company_id: int,
    end_date: date,
) -> list[dict]:
    """
    Load historical share-capital records for a company.

    Only records with effective_date <= end_date are returned.
    The caller selects the latest applicable record for each
    trading date.

    Returns:
        [
            {
                "effective_date": date(...),
                "shares_outstanding": Decimal(...)
            },
            ...
        ]
    """

    query = text(
        """
        SELECT
            effective_date,
            shares_outstanding
        FROM share_capital
        WHERE company_id = :company_id
          AND effective_date <= :end_date
          AND share_type = 'EQUITY'
          AND shares_outstanding IS NOT NULL
        ORDER BY effective_date ASC
        """
    )

    with engine.begin() as conn:
        rows = conn.execute(
            query,
            {
                "company_id": company_id,
                "end_date": end_date,
            },
        ).mappings().all()

    return [
        {
            "effective_date": row["effective_date"],
            "shares_outstanding": row["shares_outstanding"],
        }
        for row in rows
    ]


def build_market_metrics_for_company(
    company_id: int,
    start_date: date,
    end_date: date,
) -> int:
    """
    Build market metrics for one company over a date range.

    Market cap is calculated as:

        market_cap = close_price * shares_outstanding

    For each trading date, the shares outstanding value is taken
    from the latest share-capital record whose effective_date is
    <= the trading date.

    Returns:
        Number of market_metrics rows written.
    """

    from bisect import bisect_right

    # ------------------------------------------------------------
    # 1. Load all available price rows for this company.
    # ------------------------------------------------------------
    all_price_rows = _load_prices(company_id=company_id)

    # ------------------------------------------------------------
    # 2. Apply requested date range.
    # ------------------------------------------------------------
    price_rows = [
        row
        for row in all_price_rows
        if start_date <= row["trade_date"] <= end_date
    ]

    if not price_rows:
        return 0

    # ------------------------------------------------------------
    # 3. Load historical share-capital data.
    # ------------------------------------------------------------
    share_rows = _load_share_data(
        company_id=company_id,
        end_date=end_date,
    )

    # ------------------------------------------------------------
    # 4. Prepare sorted share-capital dates and values.
    # ------------------------------------------------------------
    share_dates = []
    share_values = []

    for row in share_rows:
        effective_date = row["effective_date"]
        shares_outstanding = row["shares_outstanding"]

        if effective_date is None:
            continue

        if shares_outstanding is None:
            continue

        share_dates.append(effective_date)
        share_values.append(shares_outstanding)

    if share_dates:
        combined = sorted(
            zip(share_dates, share_values),
            key=lambda item: item[0],
        )

        share_dates = [item[0] for item in combined]
        share_values = [item[1] for item in combined]

    # ------------------------------------------------------------
    # 5. Build market metrics.
    # ------------------------------------------------------------
    metrics = []

    for row in price_rows:
        trade_date = row["trade_date"]
        close_price = row.get("close_price")
        vwap = row.get("vwap")
        volume = row.get("volume")

        shares_outstanding = None
        share_data_date = None

        # --------------------------------------------------------
        # Find latest share-capital record where:
        #
        # effective_date <= trade_date
        # --------------------------------------------------------
        if share_dates:
            idx = bisect_right(share_dates, trade_date) - 1

            if idx >= 0:
                share_data_date = share_dates[idx]
                shares_outstanding = share_values[idx]

        # --------------------------------------------------------
        # Calculate market cap.
        #
        # Missing share data remains NULL.
        # Do NOT convert missing data to zero.
        # --------------------------------------------------------
        market_cap = _calculate_market_cap(
            close_price=close_price,
            shares_outstanding=shares_outstanding,
        )

        if market_cap is not None:
            calculation_method = "CLOSE_X_HISTORICAL_SHARES"
        else:
            calculation_method = "PRICE_ONLY"

        metrics.append(
            {
                "company_id": company_id,
                "trade_date": trade_date,
                "close_price": close_price,
                "vwap": vwap,
                "volume": volume,
                "shares_outstanding": shares_outstanding,
                "share_data_date": share_data_date,
                "market_cap": market_cap,
                "price_source": "NSE",
                "share_source": (
                    "NSE"
                    if shares_outstanding is not None
                    else None
                ),
                "calculation_method": calculation_method,
            }
        )

    # ------------------------------------------------------------
    # 6. Persist.
    # ------------------------------------------------------------
    if not metrics:
        return 0

    return _upsert_market_metrics(metrics)


def _upsert_market_metrics(
    rows: list[dict[str, Any]],
) -> int:

    if not rows:
        return 0

    sql = text(
        """
        INSERT INTO market_metrics (
            company_id,
            trade_date,
            close_price,
            vwap,
            volume,
            shares_outstanding,
            share_data_date,
            market_cap,
            price_source,
            share_source,
            calculation_method,
            updated_at
        )
        VALUES (
            :company_id,
            :trade_date,
            :close_price,
            :vwap,
            :volume,
            :shares_outstanding,
            :share_data_date,
            :market_cap,
            :price_source,
            :share_source,
            :calculation_method,
            NOW()
        )
        ON CONFLICT (
            company_id,
            trade_date
        )
        DO UPDATE SET
            close_price = EXCLUDED.close_price,
            vwap = EXCLUDED.vwap,
            volume = EXCLUDED.volume,
            shares_outstanding = EXCLUDED.shares_outstanding,
            share_data_date = EXCLUDED.share_data_date,
            market_cap = EXCLUDED.market_cap,
            price_source = EXCLUDED.price_source,
            share_source = EXCLUDED.share_source,
            calculation_method = EXCLUDED.calculation_method,
            updated_at = NOW()
        """
    )

    with engine.begin() as conn:
        conn.execute(sql, rows)

    return len(rows)