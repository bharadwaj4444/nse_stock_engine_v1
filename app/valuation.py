from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db import engine


DEFAULT_SCOPE = "Consolidated"


def _ratio(
    numerator: Decimal | None,
    denominator: Decimal | None,
) -> Decimal | None:
    if numerator is None or denominator is None:
        return None

    if denominator == 0:
        return None

    return numerator / denominator


def _get_market_metric(
    session: Session,
    company_id: int,
    valuation_date: date,
) -> dict | None:
    row = session.execute(
        text(
            """
            SELECT
                trade_date,
                market_cap,
                close_price,
                shares_outstanding,
                share_data_date
            FROM market_metrics
            WHERE company_id = :company_id
              AND trade_date = :valuation_date
            LIMIT 1
            """
        ),
        {
            "company_id": company_id,
            "valuation_date": valuation_date,
        },
    ).mappings().first()

    return dict(row) if row else None


def _get_ttm_as_of(
    session: Session,
    company_id: int,
    statement_scope: str,
    valuation_date: date,
) -> dict | None:
    row = session.execute(
        text(
            """
            SELECT
                period_end,
                latest_filing_date,

                revenue_ttm,
                ebitda_ttm,
                net_income_ttm,
                free_cash_flow_ttm,

                total_debt,
                cash_and_equivalents

            FROM ttm_financials
            WHERE company_id = :company_id
              AND statement_scope = :statement_scope
              AND latest_filing_date <= :valuation_date
            ORDER BY
                period_end DESC,
                latest_filing_date DESC
            LIMIT 1
            """
        ),
        {
            "company_id": company_id,
            "statement_scope": statement_scope,
            "valuation_date": valuation_date,
        },
    ).mappings().first()

    return dict(row) if row else None


def calculate_valuation(
    session: Session,
    company_id: int,
    valuation_date: date,
    statement_scope: str = DEFAULT_SCOPE,
) -> dict | None:
    """
    Calculate a point-in-time valuation.

    Market data:
        exact market_metrics.trade_date = valuation_date

    Fundamentals:
        latest TTM where latest_filing_date <= valuation_date
    """

    market = _get_market_metric(
        session,
        company_id,
        valuation_date,
    )

    if market is None:
        return None

    ttm = _get_ttm_as_of(
        session,
        company_id,
        statement_scope,
        valuation_date,
    )

    if ttm is None:
        return None

    market_cap = market["market_cap"]

    revenue = ttm["revenue_ttm"]
    ebitda = ttm["ebitda_ttm"]
    net_income = ttm["net_income_ttm"]
    free_cash_flow = ttm["free_cash_flow_ttm"]

    debt = ttm["total_debt"]
    cash = ttm["cash_and_equivalents"]

    # Enterprise value requires both debt and cash.
    if (
        market_cap is not None
        and debt is not None
        and cash is not None
    ):
        enterprise_value = (
            market_cap
            + debt
            - cash
        )
    else:
        enterprise_value = None

    return {
        "company_id": company_id,
        "valuation_date": valuation_date,
        "statement_scope": statement_scope,

        "market_cap": market_cap,
        "enterprise_value": enterprise_value,

        "ttm_period_end": ttm["period_end"],
        "ttm_filing_date": ttm["latest_filing_date"],

        "pe_ratio": _ratio(
            market_cap,
            net_income,
        ),

        "price_to_sales": _ratio(
            market_cap,
            revenue,
        ),

        "price_to_fcf": _ratio(
            market_cap,
            free_cash_flow,
        ),

        "ev_to_ebitda": _ratio(
            enterprise_value,
            ebitda,
        ),

        "ev_to_sales": _ratio(
            enterprise_value,
            revenue,
        ),

        "earnings_yield": _ratio(
            net_income,
            market_cap,
        ),

        "fcf_yield": _ratio(
            free_cash_flow,
            market_cap,
        ),

        "calculation_method": (
            "EXACT_MARKET_DATE_PIT_TTM"
        ),

        "source": "DERIVED",
    }


def upsert_valuation(
    session: Session,
    valuation: dict,
) -> None:
    session.execute(
        text(
            """
            INSERT INTO valuation_metrics (
                company_id,
                valuation_date,
                statement_scope,

                market_cap,
                enterprise_value,

                ttm_period_end,
                ttm_filing_date,

                pe_ratio,
                price_to_sales,
                price_to_fcf,
                ev_to_ebitda,
                ev_to_sales,

                earnings_yield,
                fcf_yield,

                calculation_method,
                source
            )
            VALUES (
                :company_id,
                :valuation_date,
                :statement_scope,

                :market_cap,
                :enterprise_value,

                :ttm_period_end,
                :ttm_filing_date,

                :pe_ratio,
                :price_to_sales,
                :price_to_fcf,
                :ev_to_ebitda,
                :ev_to_sales,

                :earnings_yield,
                :fcf_yield,

                :calculation_method,
                :source
            )
            ON CONFLICT (
                company_id,
                valuation_date,
                statement_scope
            )
            DO UPDATE SET
                market_cap = EXCLUDED.market_cap,
                enterprise_value = EXCLUDED.enterprise_value,

                ttm_period_end = EXCLUDED.ttm_period_end,
                ttm_filing_date = EXCLUDED.ttm_filing_date,

                pe_ratio = EXCLUDED.pe_ratio,
                price_to_sales = EXCLUDED.price_to_sales,
                price_to_fcf = EXCLUDED.price_to_fcf,
                ev_to_ebitda = EXCLUDED.ev_to_ebitda,
                ev_to_sales = EXCLUDED.ev_to_sales,

                earnings_yield = EXCLUDED.earnings_yield,
                fcf_yield = EXCLUDED.fcf_yield,

                calculation_method = EXCLUDED.calculation_method,
                source = EXCLUDED.source,

                updated_at = NOW()
            """
        ),
        valuation,
    )


def build_valuation_for_date(
    company_id: int,
    valuation_date: date,
    statement_scope: str = DEFAULT_SCOPE,
) -> dict | None:
    with Session(engine) as session:
        valuation = calculate_valuation(
            session,
            company_id,
            valuation_date,
            statement_scope,
        )

        if valuation is None:
            return None

        upsert_valuation(
            session,
            valuation,
        )

        session.commit()

        return valuation

def build_valuations_for_company(
    company_id: int,
    start_date: date,
    end_date: date,
    statement_scope: str = DEFAULT_SCOPE,
) -> int:
    """
    Build point-in-time valuations for all available market dates
    for one company.
    """

    written = 0

    with Session(engine) as session:
        market_rows = session.execute(
            text(
                """
                SELECT
                    trade_date
                FROM market_metrics
                WHERE company_id = :company_id
                  AND trade_date BETWEEN :start_date AND :end_date
                ORDER BY trade_date
                """
            ),
            {
                "company_id": company_id,
                "start_date": start_date,
                "end_date": end_date,
            },
        ).scalars().all()

        for valuation_date in market_rows:
            valuation = calculate_valuation(
                session,
                company_id,
                valuation_date,
                statement_scope,
            )

            if valuation is None:
                continue

            upsert_valuation(
                session,
                valuation,
            )

            written += 1

        session.commit()

    return written


def build_valuations_for_all_companies(
    start_date: date,
    end_date: date,
    statement_scope: str = DEFAULT_SCOPE,
) -> tuple[int, int]:
    """
    Build historical point-in-time valuations for all companies.

    Returns:
        (companies_processed, valuation_rows_written)
    """

    with Session(engine) as session:
        company_ids = session.execute(
            text(
                """
                SELECT id
                FROM companies
                WHERE is_active = TRUE
                ORDER BY id
                """
            )
        ).scalars().all()

    companies_processed = 0
    rows_written = 0

    for company_id in company_ids:
        try:
            written = build_valuations_for_company(
                company_id,
                start_date,
                end_date,
                statement_scope,
            )

            companies_processed += 1
            rows_written += written

            if companies_processed % 100 == 0:
                print(
                    f"[{companies_processed}/{len(company_ids)}] "
                    f"company_id={company_id} "
                    f"rows={rows_written}"
                )

        except Exception as exc:
            print(
                f"FAILED company_id={company_id}: "
                f"{type(exc).__name__}: {exc}"
            )

    return companies_processed, rows_written