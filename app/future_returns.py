from __future__ import annotations

from datetime import date
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db import engine


CALCULATION_METHOD = "TRADING_DAY_FORWARD_RETURN_V1"


def build_future_returns(
    start_date: date,
    end_date: date,
    session: Session | None = None,
) -> int:
    own_session = session is None

    if own_session:
        session = Session(engine)

    try:
        sql = text(
            """
            INSERT INTO future_returns (
                company_id,
                trade_date,
                close_price,
                close_5d,
                close_20d,
                close_60d,
                forward_5d_return,
                forward_20d_return,
                forward_60d_return,
                calculation_method
            )
            SELECT
                company_id,
                trade_date,
                close_price,

                LEAD(close_price, 5) OVER (
                    PARTITION BY company_id
                    ORDER BY trade_date
                ) AS close_5d,

                LEAD(close_price, 20) OVER (
                    PARTITION BY company_id
                    ORDER BY trade_date
                ) AS close_20d,

                LEAD(close_price, 60) OVER (
                    PARTITION BY company_id
                    ORDER BY trade_date
                ) AS close_60d,

                CASE
                    WHEN close_price > 0
                     AND LEAD(close_price, 5) OVER (
                         PARTITION BY company_id
                         ORDER BY trade_date
                     ) > 0
                    THEN
                        LEAD(close_price, 5) OVER (
                            PARTITION BY company_id
                            ORDER BY trade_date
                        ) / close_price - 1
                    ELSE NULL
                END AS forward_5d_return,

                CASE
                    WHEN close_price > 0
                     AND LEAD(close_price, 20) OVER (
                         PARTITION BY company_id
                         ORDER BY trade_date
                     ) > 0
                    THEN
                        LEAD(close_price, 20) OVER (
                            PARTITION BY company_id
                            ORDER BY trade_date
                        ) / close_price - 1
                    ELSE NULL
                END AS forward_20d_return,

                CASE
                    WHEN close_price > 0
                     AND LEAD(close_price, 60) OVER (
                         PARTITION BY company_id
                         ORDER BY trade_date
                     ) > 0
                    THEN
                        LEAD(close_price, 60) OVER (
                            PARTITION BY company_id
                            ORDER BY trade_date
                        ) / close_price - 1
                    ELSE NULL
                END AS forward_60d_return,

                :calculation_method

            FROM daily_prices
            WHERE trade_date BETWEEN :start_date AND :end_date

            ON CONFLICT (company_id, trade_date)
            DO UPDATE SET
                close_price = EXCLUDED.close_price,
                close_5d = EXCLUDED.close_5d,
                close_20d = EXCLUDED.close_20d,
                close_60d = EXCLUDED.close_60d,
                forward_5d_return = EXCLUDED.forward_5d_return,
                forward_20d_return = EXCLUDED.forward_20d_return,
                forward_60d_return = EXCLUDED.forward_60d_return,
                calculation_method = EXCLUDED.calculation_method,
                updated_at = NOW()
            """
        )

        result = session.execute(
            sql,
            {
                "start_date": start_date,
                "end_date": end_date,
                "calculation_method": CALCULATION_METHOD,
            },
        )

        session.commit()
        return result.rowcount or 0

    finally:
        if own_session:
            session.close()