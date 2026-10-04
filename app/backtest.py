from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db import engine


def run_decile_backtest(
    start_date,
    end_date,
    session: Session | None = None,
):
    own_session = session is None

    if own_session:
        session = Session(engine)

    try:
        sql = text(
            """
            WITH ranked AS (
                SELECT
                    r.company_id,
                    r.trade_date,
                    r.overall_score,

                    NTILE(10) OVER (
                        PARTITION BY r.trade_date
                        ORDER BY r.overall_score DESC
                    ) AS decile

                FROM stock_rankings r

                WHERE r.trade_date BETWEEN :start_date AND :end_date
                  AND r.overall_score IS NOT NULL
            ),

            joined AS (
                SELECT
                    r.trade_date,
                    r.decile,
                    f.forward_5d_return,
                    f.forward_20d_return,
                    f.forward_60d_return

                FROM ranked r

                JOIN future_returns f
                  ON f.company_id = r.company_id
                 AND f.trade_date = r.trade_date
            )

            SELECT
                decile,

                COUNT(*) AS observations,
                COUNT(DISTINCT trade_date) AS ranking_dates,

                COUNT(forward_5d_return) AS observations_5d,
                AVG(forward_5d_return) AS avg_5d,
                PERCENTILE_CONT(0.5)
                    WITHIN GROUP (ORDER BY forward_5d_return)
                    AS median_5d,

                AVG(
                    CASE
                        WHEN forward_5d_return > 0 THEN 1.0
                        WHEN forward_5d_return IS NOT NULL THEN 0.0
                    END
                ) AS hit_rate_5d,

                COUNT(forward_20d_return) AS observations_20d,
                AVG(forward_20d_return) AS avg_20d,
                PERCENTILE_CONT(0.5)
                    WITHIN GROUP (ORDER BY forward_20d_return)
                    AS median_20d,

                AVG(
                    CASE
                        WHEN forward_20d_return > 0 THEN 1.0
                        WHEN forward_20d_return IS NOT NULL THEN 0.0
                    END
                ) AS hit_rate_20d,

                COUNT(forward_60d_return) AS observations_60d,
                AVG(forward_60d_return) AS avg_60d,
                PERCENTILE_CONT(0.5)
                    WITHIN GROUP (ORDER BY forward_60d_return)
                    AS median_60d,

                AVG(
                    CASE
                        WHEN forward_60d_return > 0 THEN 1.0
                        WHEN forward_60d_return IS NOT NULL THEN 0.0
                    END
                ) AS hit_rate_60d

            FROM joined

            GROUP BY decile

            ORDER BY decile
            """
        )

        rows = session.execute(
            sql,
            {
                "start_date": start_date,
                "end_date": end_date,
            },
        ).mappings().all()

        return rows

    finally:
        if own_session:
            session.close()