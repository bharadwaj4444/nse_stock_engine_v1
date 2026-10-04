from __future__ import annotations

from datetime import date

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db import SessionLocal


CALCULATION_METHOD = "CROSS_SECTIONAL_PERCENTILE_V1"
STATEMENT_SCOPE = "Consolidated"


def build_feature_scores(
    start_date: date,
    end_date: date,
    session: Session | None = None,
) -> int:
    """
    Build cross-sectional percentile scores.

    Each feature is ranked independently within each trading date
    and only against observations valid for that feature.
    """

    owns_session = session is None
    session = session or SessionLocal()

    try:
        sql = text(
            """
            WITH base AS (
                SELECT
                    company_id,
                    trade_date,
                    statement_scope,

                    return_5d,
                    return_20d,
                    return_60d,
                    return_120d,

                    roe,
                    roa,
                    ebitda_margin,
                    ebit_margin,
                    net_profit_margin,

                    debt_to_equity,
                    debt_to_ebitda,
                    net_debt_to_ebitda,

                    pe_ratio,
                    price_to_sales,
                    ev_to_ebitda,
                    earnings_yield

                FROM historical_features
                WHERE trade_date BETWEEN :start_date AND :end_date
                  AND statement_scope = :statement_scope
            ),

            r_return_5d AS (
                SELECT
                    company_id,
                    trade_date,
                    percent_rank() OVER (
                        PARTITION BY trade_date
                        ORDER BY return_5d
                    ) AS score
                FROM base
                WHERE return_5d IS NOT NULL
                  AND return_5d <> 'NaN'::numeric
            ),

            r_return_20d AS (
                SELECT
                    company_id,
                    trade_date,
                    percent_rank() OVER (
                        PARTITION BY trade_date
                        ORDER BY return_20d
                    ) AS score
                FROM base
                WHERE return_20d IS NOT NULL
                  AND return_20d <> 'NaN'::numeric
            ),

            r_return_60d AS (
                SELECT
                    company_id,
                    trade_date,
                    percent_rank() OVER (
                        PARTITION BY trade_date
                        ORDER BY return_60d
                    ) AS score
                FROM base
                WHERE return_60d IS NOT NULL
                  AND return_60d <> 'NaN'::numeric
            ),

            r_return_120d AS (
                SELECT
                    company_id,
                    trade_date,
                    percent_rank() OVER (
                        PARTITION BY trade_date
                        ORDER BY return_120d
                    ) AS score
                FROM base
                WHERE return_120d IS NOT NULL
                  AND return_120d <> 'NaN'::numeric
            ),

            r_roe AS (
                SELECT
                    company_id,
                    trade_date,
                    percent_rank() OVER (
                        PARTITION BY trade_date
                        ORDER BY roe
                    ) AS score
                FROM base
                WHERE roe IS NOT NULL
                  AND roe <> 'NaN'::numeric
            ),

            r_roa AS (
                SELECT
                    company_id,
                    trade_date,
                    percent_rank() OVER (
                        PARTITION BY trade_date
                        ORDER BY roa
                    ) AS score
                FROM base
                WHERE roa IS NOT NULL
                  AND roa <> 'NaN'::numeric
            ),

            r_ebitda_margin AS (
                SELECT
                    company_id,
                    trade_date,
                    percent_rank() OVER (
                        PARTITION BY trade_date
                        ORDER BY ebitda_margin
                    ) AS score
                FROM base
                WHERE ebitda_margin IS NOT NULL
                  AND ebitda_margin <> 'NaN'::numeric
            ),

            r_ebit_margin AS (
                SELECT
                    company_id,
                    trade_date,
                    percent_rank() OVER (
                        PARTITION BY trade_date
                        ORDER BY ebit_margin
                    ) AS score
                FROM base
                WHERE ebit_margin IS NOT NULL
                  AND ebit_margin <> 'NaN'::numeric
            ),

            r_net_profit_margin AS (
                SELECT
                    company_id,
                    trade_date,
                    percent_rank() OVER (
                        PARTITION BY trade_date
                        ORDER BY net_profit_margin
                    ) AS score
                FROM base
                WHERE net_profit_margin IS NOT NULL
                  AND net_profit_margin <> 'NaN'::numeric
            ),

            r_debt_to_equity AS (
                SELECT
                    company_id,
                    trade_date,
                    percent_rank() OVER (
                        PARTITION BY trade_date
                        ORDER BY debt_to_equity
                    ) AS score
                FROM base
                WHERE debt_to_equity IS NOT NULL
                  AND debt_to_equity <> 'NaN'::numeric
                  AND debt_to_equity >= 0
            ),

            r_debt_to_ebitda AS (
                SELECT
                    company_id,
                    trade_date,
                    percent_rank() OVER (
                        PARTITION BY trade_date
                        ORDER BY debt_to_ebitda
                    ) AS score
                FROM base
                WHERE debt_to_ebitda IS NOT NULL
                  AND debt_to_ebitda <> 'NaN'::numeric
                  AND debt_to_ebitda > 0
            ),

            r_net_debt_to_ebitda AS (
                SELECT
                    company_id,
                    trade_date,
                    percent_rank() OVER (
                        PARTITION BY trade_date
                        ORDER BY net_debt_to_ebitda
                    ) AS score
                FROM base
                WHERE net_debt_to_ebitda IS NOT NULL
                  AND net_debt_to_ebitda <> 'NaN'::numeric
            ),

            r_pe AS (
                SELECT
                    company_id,
                    trade_date,
                    percent_rank() OVER (
                        PARTITION BY trade_date
                        ORDER BY pe_ratio
                    ) AS score
                FROM base
                WHERE pe_ratio IS NOT NULL
                  AND pe_ratio <> 'NaN'::numeric
                  AND pe_ratio > 0
            ),

            r_price_to_sales AS (
                SELECT
                    company_id,
                    trade_date,
                    percent_rank() OVER (
                        PARTITION BY trade_date
                        ORDER BY price_to_sales
                    ) AS score
                FROM base
                WHERE price_to_sales IS NOT NULL
                  AND price_to_sales <> 'NaN'::numeric
                  AND price_to_sales > 0
            ),

            r_ev_to_ebitda AS (
                SELECT
                    company_id,
                    trade_date,
                    percent_rank() OVER (
                        PARTITION BY trade_date
                        ORDER BY ev_to_ebitda
                    ) AS score
                FROM base
                WHERE ev_to_ebitda IS NOT NULL
                  AND ev_to_ebitda <> 'NaN'::numeric
                  AND ev_to_ebitda > 0
            ),

            r_earnings_yield AS (
                SELECT
                    company_id,
                    trade_date,
                    percent_rank() OVER (
                        PARTITION BY trade_date
                        ORDER BY earnings_yield
                    ) AS score
                FROM base
                WHERE earnings_yield IS NOT NULL
                  AND earnings_yield <> 'NaN'::numeric
            )

            INSERT INTO historical_feature_scores (
                company_id,
                trade_date,
                statement_scope,

                return_5d_score,
                return_20d_score,
                return_60d_score,
                return_120d_score,

                roe_score,
                roa_score,
                ebitda_margin_score,
                ebit_margin_score,
                net_profit_margin_score,

                debt_to_equity_score,
                debt_to_ebitda_score,
                net_debt_to_ebitda_score,

                pe_score,
                price_to_sales_score,
                ev_to_ebitda_score,
                earnings_yield_score,

                calculation_method,
                created_at,
                updated_at
            )

            SELECT
                b.company_id,
                b.trade_date,
                b.statement_scope,

                r5.score,
                r20.score,
                r60.score,
                r120.score,

                rr.roe_score,
                rr.roa_score,
                rr.ebitda_margin_score,
                rr.ebit_margin_score,
                rr.net_profit_margin_score,

                CASE
                    WHEN rde.score IS NOT NULL
                    THEN 1 - rde.score
                END,

                CASE
                    WHEN rdeb.score IS NOT NULL
                    THEN 1 - rdeb.score
                END,

                CASE
                    WHEN rndeb.score IS NOT NULL
                    THEN 1 - rndeb.score
                END,

                CASE
                    WHEN rpe.score IS NOT NULL
                    THEN 1 - rpe.score
                END,

                CASE
                    WHEN rps.score IS NOT NULL
                    THEN 1 - rps.score
                END,

                CASE
                    WHEN rev.score IS NOT NULL
                    THEN 1 - rev.score
                END,

                rey.score,

                :calculation_method,
                CURRENT_TIMESTAMP,
                CURRENT_TIMESTAMP

            FROM base b

            LEFT JOIN r_return_5d r5
                ON r5.company_id = b.company_id
               AND r5.trade_date = b.trade_date

            LEFT JOIN r_return_20d r20
                ON r20.company_id = b.company_id
               AND r20.trade_date = b.trade_date

            LEFT JOIN r_return_60d r60
                ON r60.company_id = b.company_id
               AND r60.trade_date = b.trade_date

            LEFT JOIN r_return_120d r120
                ON r120.company_id = b.company_id
               AND r120.trade_date = b.trade_date

            LEFT JOIN (
                SELECT
                    company_id,
                    trade_date,
                    MAX(roe_score) AS roe_score,
                    MAX(roa_score) AS roa_score,
                    MAX(ebitda_margin_score) AS ebitda_margin_score,
                    MAX(ebit_margin_score) AS ebit_margin_score,
                    MAX(net_profit_margin_score) AS net_profit_margin_score
                FROM (
                    SELECT company_id, trade_date, score AS roe_score,
                           NULL::double precision AS roa_score,
                           NULL::double precision AS ebitda_margin_score,
                           NULL::double precision AS ebit_margin_score,
                           NULL::double precision AS net_profit_margin_score
                    FROM r_roe

                    UNION ALL

                    SELECT company_id, trade_date, NULL, score, NULL, NULL, NULL
                    FROM r_roa

                    UNION ALL

                    SELECT company_id, trade_date, NULL, NULL, score, NULL, NULL
                    FROM r_ebitda_margin

                    UNION ALL

                    SELECT company_id, trade_date, NULL, NULL, NULL, score, NULL
                    FROM r_ebit_margin

                    UNION ALL

                    SELECT company_id, trade_date, NULL, NULL, NULL, NULL, score
                    FROM r_net_profit_margin
                ) x
                GROUP BY company_id, trade_date
            ) rr
                ON rr.company_id = b.company_id
               AND rr.trade_date = b.trade_date

            LEFT JOIN r_debt_to_equity rde
                ON rde.company_id = b.company_id
               AND rde.trade_date = b.trade_date

            LEFT JOIN r_debt_to_ebitda rdeb
                ON rdeb.company_id = b.company_id
               AND rdeb.trade_date = b.trade_date

            LEFT JOIN r_net_debt_to_ebitda rndeb
                ON rndeb.company_id = b.company_id
               AND rndeb.trade_date = b.trade_date

            LEFT JOIN r_pe rpe
                ON rpe.company_id = b.company_id
               AND rpe.trade_date = b.trade_date

            LEFT JOIN r_price_to_sales rps
                ON rps.company_id = b.company_id
               AND rps.trade_date = b.trade_date

            LEFT JOIN r_ev_to_ebitda rev
                ON rev.company_id = b.company_id
               AND rev.trade_date = b.trade_date

            LEFT JOIN r_earnings_yield rey
                ON rey.company_id = b.company_id
               AND rey.trade_date = b.trade_date

            ON CONFLICT (
                company_id,
                trade_date,
                statement_scope
            )
            DO UPDATE SET
                return_5d_score = EXCLUDED.return_5d_score,
                return_20d_score = EXCLUDED.return_20d_score,
                return_60d_score = EXCLUDED.return_60d_score,
                return_120d_score = EXCLUDED.return_120d_score,

                roe_score = EXCLUDED.roe_score,
                roa_score = EXCLUDED.roa_score,
                ebitda_margin_score =
                    EXCLUDED.ebitda_margin_score,
                ebit_margin_score =
                    EXCLUDED.ebit_margin_score,
                net_profit_margin_score =
                    EXCLUDED.net_profit_margin_score,

                debt_to_equity_score =
                    EXCLUDED.debt_to_equity_score,
                debt_to_ebitda_score =
                    EXCLUDED.debt_to_ebitda_score,
                net_debt_to_ebitda_score =
                    EXCLUDED.net_debt_to_ebitda_score,

                pe_score = EXCLUDED.pe_score,
                price_to_sales_score =
                    EXCLUDED.price_to_sales_score,
                ev_to_ebitda_score =
                    EXCLUDED.ev_to_ebitda_score,
                earnings_yield_score =
                    EXCLUDED.earnings_yield_score,

                calculation_method =
                    EXCLUDED.calculation_method,
                updated_at = CURRENT_TIMESTAMP
            """
        )

        result = session.execute(
            sql,
            {
                "start_date": start_date,
                "end_date": end_date,
                "statement_scope": STATEMENT_SCOPE,
                "calculation_method": CALCULATION_METHOD,
            },
        )

        session.commit()
        return result.rowcount or 0

    except Exception:
        session.rollback()
        raise

    finally:
        if owns_session:
            session.close()