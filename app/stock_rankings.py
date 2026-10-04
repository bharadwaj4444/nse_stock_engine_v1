from datetime import date

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db import SessionLocal


CALCULATION_METHOD = "V1_CATEGORY_WEIGHTED_NORMALIZED"
STATEMENT_SCOPE = "Consolidated"


def build_stock_rankings(
    start_date: date,
    end_date: date,
    session: Session | None = None,
) -> int:
    """
    Build PIT stock rankings from historical feature scores.

    Category weights:

        Momentum       30%
        Profitability  30%
        Leverage       15%
        Valuation      25%

    Individual feature weights:

        Momentum:
            return_5d       15%
            return_20d      30%
            return_60d      30%
            return_120d     25%

        Profitability:
            ROE             25%
            ROA             15%
            EBITDA margin   25%
            EBIT margin     15%
            Net margin      20%

        Leverage:
            Debt/Equity     35%
            Debt/EBITDA     35%
            Net Debt/EBITDA 30%

        Valuation:
            PE              30%
            P/S             20%
            EV/EBITDA       25%
            Earnings yield  25%

    Missing features are handled by renormalizing the available
    feature weights within each category.

    A category requires at least 2 valid features.

    Overall score requires at least 3 valid categories.
    """

    own_session = session is None
    session = session or SessionLocal()

    try:
        sql = text(
            """
            WITH base AS (
                SELECT
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
                    earnings_yield_score

                FROM historical_feature_scores
                WHERE statement_scope = :statement_scope
                  AND trade_date BETWEEN :start_date AND :end_date
            ),

            category_scores AS (
                SELECT
                    *,
                    
                    -- Momentum
                    CASE
                        WHEN
                            (
                                (return_5d_score IS NOT NULL)::int
                                + (return_20d_score IS NOT NULL)::int
                                + (return_60d_score IS NOT NULL)::int
                                + (return_120d_score IS NOT NULL)::int
                            ) >= 2
                        THEN
                            (
                                COALESCE(return_5d_score * 0.15, 0)
                                + COALESCE(return_20d_score * 0.30, 0)
                                + COALESCE(return_60d_score * 0.30, 0)
                                + COALESCE(return_120d_score * 0.25, 0)
                            )
                            /
                            (
                                COALESCE((return_5d_score IS NOT NULL)::int * 0.15, 0)
                                + COALESCE((return_20d_score IS NOT NULL)::int * 0.30, 0)
                                + COALESCE((return_60d_score IS NOT NULL)::int * 0.30, 0)
                                + COALESCE((return_120d_score IS NOT NULL)::int * 0.25, 0)
                            )
                        ELSE NULL
                    END AS momentum_score,

                    -- Profitability
                    CASE
                        WHEN
                            (
                                (roe_score IS NOT NULL)::int
                                + (roa_score IS NOT NULL)::int
                                + (ebitda_margin_score IS NOT NULL)::int
                                + (ebit_margin_score IS NOT NULL)::int
                                + (net_profit_margin_score IS NOT NULL)::int
                            ) >= 2
                        THEN
                            (
                                COALESCE(roe_score * 0.25, 0)
                                + COALESCE(roa_score * 0.15, 0)
                                + COALESCE(ebitda_margin_score * 0.25, 0)
                                + COALESCE(ebit_margin_score * 0.15, 0)
                                + COALESCE(net_profit_margin_score * 0.20, 0)
                            )
                            /
                            (
                                COALESCE((roe_score IS NOT NULL)::int * 0.25, 0)
                                + COALESCE((roa_score IS NOT NULL)::int * 0.15, 0)
                                + COALESCE((ebitda_margin_score IS NOT NULL)::int * 0.25, 0)
                                + COALESCE((ebit_margin_score IS NOT NULL)::int * 0.15, 0)
                                + COALESCE((net_profit_margin_score IS NOT NULL)::int * 0.20, 0)
                            )
                        ELSE NULL
                    END AS profitability_score,

                    -- Leverage
                    CASE
                        WHEN
                            (
                                (debt_to_equity_score IS NOT NULL)::int
                                + (debt_to_ebitda_score IS NOT NULL)::int
                                + (net_debt_to_ebitda_score IS NOT NULL)::int
                            ) >= 2
                        THEN
                            (
                                COALESCE(debt_to_equity_score * 0.35, 0)
                                + COALESCE(debt_to_ebitda_score * 0.35, 0)
                                + COALESCE(net_debt_to_ebitda_score * 0.30, 0)
                            )
                            /
                            (
                                COALESCE((debt_to_equity_score IS NOT NULL)::int * 0.35, 0)
                                + COALESCE((debt_to_ebitda_score IS NOT NULL)::int * 0.35, 0)
                                + COALESCE((net_debt_to_ebitda_score IS NOT NULL)::int * 0.30, 0)
                            )
                        ELSE NULL
                    END AS leverage_score,

                    -- Valuation
                    CASE
                        WHEN
                            (
                                (pe_score IS NOT NULL)::int
                                + (price_to_sales_score IS NOT NULL)::int
                                + (ev_to_ebitda_score IS NOT NULL)::int
                                + (earnings_yield_score IS NOT NULL)::int
                            ) >= 2
                        THEN
                            (
                                COALESCE(pe_score * 0.30, 0)
                                + COALESCE(price_to_sales_score * 0.20, 0)
                                + COALESCE(ev_to_ebitda_score * 0.25, 0)
                                + COALESCE(earnings_yield_score * 0.25, 0)
                            )
                            /
                            (
                                COALESCE((pe_score IS NOT NULL)::int * 0.30, 0)
                                + COALESCE((price_to_sales_score IS NOT NULL)::int * 0.20, 0)
                                + COALESCE((ev_to_ebitda_score IS NOT NULL)::int * 0.25, 0)
                                + COALESCE((earnings_yield_score IS NOT NULL)::int * 0.25, 0)
                            )
                        ELSE NULL
                    END AS valuation_score

                FROM base
            ),

            with_counts AS (
                SELECT
                    *,
                    
                    (
                        (return_5d_score IS NOT NULL)::int
                        + (return_20d_score IS NOT NULL)::int
                        + (return_60d_score IS NOT NULL)::int
                        + (return_120d_score IS NOT NULL)::int
                        + (roe_score IS NOT NULL)::int
                        + (roa_score IS NOT NULL)::int
                        + (ebitda_margin_score IS NOT NULL)::int
                        + (ebit_margin_score IS NOT NULL)::int
                        + (net_profit_margin_score IS NOT NULL)::int
                        + (debt_to_equity_score IS NOT NULL)::int
                        + (debt_to_ebitda_score IS NOT NULL)::int
                        + (net_debt_to_ebitda_score IS NOT NULL)::int
                        + (pe_score IS NOT NULL)::int
                        + (price_to_sales_score IS NOT NULL)::int
                        + (ev_to_ebitda_score IS NOT NULL)::int
                        + (earnings_yield_score IS NOT NULL)::int
                    ) AS valid_feature_count,

                    (
                        (momentum_score IS NOT NULL)::int
                        + (profitability_score IS NOT NULL)::int
                        + (leverage_score IS NOT NULL)::int
                        + (valuation_score IS NOT NULL)::int
                    ) AS valid_category_count

                FROM category_scores
            ),

            scored AS (
                SELECT
                    *,
                    CASE
                        WHEN valid_category_count >= 3
                        THEN
                            (
                                COALESCE(momentum_score * 0.30, 0)
                                + COALESCE(profitability_score * 0.30, 0)
                                + COALESCE(leverage_score * 0.15, 0)
                                + COALESCE(valuation_score * 0.25, 0)
                            )
                            /
                            (
                                COALESCE((momentum_score IS NOT NULL)::int * 0.30, 0)
                                + COALESCE((profitability_score IS NOT NULL)::int * 0.30, 0)
                                + COALESCE((leverage_score IS NOT NULL)::int * 0.15, 0)
                                + COALESCE((valuation_score IS NOT NULL)::int * 0.25, 0)
                            )
                        ELSE NULL
                    END AS overall_score

                FROM with_counts
            ),

            ranked_valid AS (
                SELECT
                    *,
                    RANK() OVER (
                        PARTITION BY trade_date
                        ORDER BY overall_score DESC
                    ) AS overall_rank,

                    PERCENT_RANK() OVER (
                        PARTITION BY trade_date
                        ORDER BY overall_score DESC
                    ) AS raw_percentile

                FROM scored
                WHERE overall_score IS NOT NULL
            ),

            ranked AS (
                SELECT
                    s.*,
                    rv.overall_rank,
                    1 - rv.raw_percentile AS overall_percentile
                FROM scored s
                LEFT JOIN ranked_valid rv
                    ON rv.company_id = s.company_id
                AND rv.trade_date = s.trade_date
                AND rv.statement_scope = s.statement_scope
            )

            INSERT INTO stock_rankings (
                company_id,
                trade_date,
                statement_scope,

                momentum_score,
                profitability_score,
                leverage_score,
                valuation_score,

                overall_score,
                overall_rank,
                overall_percentile,

                valid_feature_count,
                valid_category_count,

                calculation_method,
                created_at,
                updated_at
            )

            SELECT
                company_id,
                trade_date,
                statement_scope,

                momentum_score,
                profitability_score,
                leverage_score,
                valuation_score,

                overall_score,
                overall_rank,

                overall_percentile,

                valid_feature_count,
                valid_category_count,

                :calculation_method,
                NOW(),
                NOW()

            FROM ranked

            ON CONFLICT (
                company_id,
                trade_date,
                statement_scope
            )
            DO UPDATE SET

                momentum_score = EXCLUDED.momentum_score,
                profitability_score = EXCLUDED.profitability_score,
                leverage_score = EXCLUDED.leverage_score,
                valuation_score = EXCLUDED.valuation_score,

                overall_score = EXCLUDED.overall_score,
                overall_rank = EXCLUDED.overall_rank,
                overall_percentile = EXCLUDED.overall_percentile,

                valid_feature_count = EXCLUDED.valid_feature_count,
                valid_category_count = EXCLUDED.valid_category_count,

                calculation_method = EXCLUDED.calculation_method,
                updated_at = NOW()
            """
        )

        result = session.execute(
            sql,
            {
                "statement_scope": STATEMENT_SCOPE,
                "start_date": start_date,
                "end_date": end_date,
                "calculation_method": CALCULATION_METHOD,
            },
        )

        session.commit()

        return result.rowcount or 0

    except Exception:
        session.rollback()
        raise

    finally:
        if own_session:
            session.close()