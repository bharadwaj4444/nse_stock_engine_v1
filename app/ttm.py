from __future__ import annotations

from collections import defaultdict
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import text

from app.db import engine


FLOW_FIELDS = (
    "revenue",
    "ebitda",
    "ebit",
    "profit_before_tax",
    "net_income",
    "operating_cash_flow",
    "capital_expenditure",
    "free_cash_flow",
)

BALANCE_FIELDS = (
    "total_assets",
    "total_equity",
    "total_debt",
    "cash_and_equivalents",
)


def _is_complete_quarter_sequence(rows: list[dict[str, Any]]) -> bool:
    """
    Return True when rows represent four consecutive calendar quarters.

    NSE financial periods normally end around Mar/Jun/Sep/Dec, but we do
    not hard-code those months. We compare the actual dates and require
    consecutive 3-month quarter steps.
    """
    if len(rows) != 4:
        return False

    periods = [row["period_end"] for row in rows]

    for previous, current in zip(periods, periods[1:]):
        month_diff = (
            (current.year - previous.year) * 12
            + current.month
            - previous.month
        )

        if month_diff != 3:
            return False

        # Quarter-end dates should be reasonably close to three months apart.
        # This also protects against accidentally mixing unrelated periods.
        if (current - previous).days < 80 or (current - previous).days > 100:
            return False

    return True


def _deduplicate_quarters(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Deduplicate financial statements to one logical quarterly statement.

    Logical identity:
        company_id + period_end + statement_scope

    Preference:
        1. filing_date present
        2. latest filing_date
        3. Revision over Original
        4. highest id
    """
    grouped: dict[tuple[int, date, str], list[dict[str, Any]]] = defaultdict(list)

    for row in rows:
        key = (
            int(row["company_id"]),
            row["period_end"],
            row["statement_scope"],
        )
        grouped[key].append(row)

    result: list[dict[str, Any]] = []

    for candidates in grouped.values():
        candidates.sort(
            key=lambda r: (
                r["filing_date"] is not None,
                r["filing_date"] or date.min,
                1 if r["submission_type"] == "Revision" else 0,
                int(r["id"]),
            ),
            reverse=True,
        )

        result.append(candidates[0])

    result.sort(
        key=lambda r: (
            int(r["company_id"]),
            r["statement_scope"],
            r["period_end"],
        )
    )

    return result


def _decimal_sum(rows: list[dict[str, Any]], field: str) -> Decimal | None:
    values = [row[field] for row in rows]

    if any(value is None for value in values):
        return None

    total = Decimal("0")

    for value in values:
        total += Decimal(value)

    return total


def _calculate_ttm_row(
    quarters: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Calculate one TTM record from four normalized quarterly statements.
    """
    latest = quarters[-1]

    filing_dates = [
        row["filing_date"]
        for row in quarters
        if row["filing_date"] is not None
    ]

    result: dict[str, Any] = {
        "company_id": latest["company_id"],
        "period_end": latest["period_end"],
        "latest_filing_date": max(filing_dates) if filing_dates else None,
        "statement_scope": latest["statement_scope"],
        "source": "DERIVED",
        "source_periods": ",".join(
            row["period_end"].isoformat() for row in quarters
        ),
        "calculation_method": "FOUR_QUARTERS",
    }

    for field in FLOW_FIELDS:
        result[f"{field}_ttm"] = _decimal_sum(quarters, field)

    # EPS is treated separately. Summing quarterly EPS is only done when
    # all four quarterly EPS values exist.
    result["eps_ttm"] = _decimal_sum(quarters, "eps")

    # Balance-sheet metrics are point-in-time values.
    #
    # Quarterly NSE filings do not always repeat the balance sheet.
    # Therefore use the latest available value at or before the TTM
    # period end rather than requiring the latest quarter itself to
    # contain balance-sheet data.
    for field in BALANCE_FIELDS:
        result[field] = None

        for row in reversed(quarters):
            value = row[field]

            if value is not None:
                result[field] = value
                break

    if result["eps_ttm"] is None:
        result["calculation_method"] = "FOUR_QUARTERS_EPS_PARTIAL"

    return result

def _load_quarterly_statements(
    company_id: int | None = None,
    statement_scope: str | None = None,
) -> list[dict[str, Any]]:
    """
    Load quarterly statements in one SQL query.

    Deduplication is performed in Python because the precedence rule is
    explicit and testable.
    """
    conditions = [
        "period_type = 'quarterly'"
    ]

    params: dict[str, Any] = {}

    if company_id is not None:
        conditions.append("company_id = :company_id")
        params["company_id"] = company_id

    if statement_scope is not None:
        conditions.append("statement_scope = :statement_scope")
        params["statement_scope"] = statement_scope

    sql = f"""
        SELECT
            id,
            company_id,
            period_end,
            filing_date,
            statement_scope,
            submission_type,
            revenue,
            ebitda,
            ebit,
            profit_before_tax,
            net_income,
            eps,
            total_assets,
            total_equity,
            total_debt,
            cash_and_equivalents,
            operating_cash_flow,
            capital_expenditure,
            free_cash_flow
        FROM financial_statements
        WHERE {" AND ".join(conditions)}
        ORDER BY company_id, statement_scope, period_end, id
    """

    with engine.connect() as conn:
        rows = conn.execute(
            text(sql),
            params,
        ).mappings().all()

    return _deduplicate_quarters([dict(row) for row in rows])

def calculate_ttm_for_company(
    company_id: int,
    statement_scope: str,
) -> list[dict[str, Any]]:
    """
    Calculate every available four-quarter TTM point for one company/scope.
    """
    rows = _load_quarterly_statements(
        company_id=company_id,
        statement_scope=statement_scope,
    )

    grouped: dict[tuple[int, str], list[dict[str, Any]]] = defaultdict(list)

    for row in rows:
        grouped[
            (
                int(row["company_id"]),
                row["statement_scope"],
            )
        ].append(row)

    results: list[dict[str, Any]] = []

    for quarters_all in grouped.values():
        quarters_all.sort(key=lambda r: r["period_end"])

        for index in range(3, len(quarters_all)):
            window = quarters_all[index - 3 : index + 1]

            if not _is_complete_quarter_sequence(window):
                continue

            results.append(_calculate_ttm_row(window))

    return results


def _upsert_ttm_rows(rows: list[dict[str, Any]]) -> int:
    if not rows:
        return 0

    sql = text(
        """
        INSERT INTO ttm_financials (
            company_id,
            period_end,
            latest_filing_date,
            statement_scope,
            revenue_ttm,
            ebitda_ttm,
            ebit_ttm,
            profit_before_tax_ttm,
            net_income_ttm,
            eps_ttm,
            operating_cash_flow_ttm,
            capital_expenditure_ttm,
            free_cash_flow_ttm,
            total_assets,
            total_equity,
            total_debt,
            cash_and_equivalents,
            calculation_method,
            source_periods,
            source
        )
        VALUES (
            :company_id,
            :period_end,
            :latest_filing_date,
            :statement_scope,
            :revenue_ttm,
            :ebitda_ttm,
            :ebit_ttm,
            :profit_before_tax_ttm,
            :net_income_ttm,
            :eps_ttm,
            :operating_cash_flow_ttm,
            :capital_expenditure_ttm,
            :free_cash_flow_ttm,
            :total_assets,
            :total_equity,
            :total_debt,
            :cash_and_equivalents,
            :calculation_method,
            :source_periods,
            :source
        )
        ON CONFLICT (company_id, period_end, statement_scope)
        DO UPDATE SET
            latest_filing_date = EXCLUDED.latest_filing_date,
            revenue_ttm = EXCLUDED.revenue_ttm,
            ebitda_ttm = EXCLUDED.ebitda_ttm,
            ebit_ttm = EXCLUDED.ebit_ttm,
            profit_before_tax_ttm = EXCLUDED.profit_before_tax_ttm,
            net_income_ttm = EXCLUDED.net_income_ttm,
            eps_ttm = EXCLUDED.eps_ttm,
            operating_cash_flow_ttm = EXCLUDED.operating_cash_flow_ttm,
            capital_expenditure_ttm = EXCLUDED.capital_expenditure_ttm,
            free_cash_flow_ttm = EXCLUDED.free_cash_flow_ttm,
            total_assets = EXCLUDED.total_assets,
            total_equity = EXCLUDED.total_equity,
            total_debt = EXCLUDED.total_debt,
            cash_and_equivalents = EXCLUDED.cash_and_equivalents,
            calculation_method = EXCLUDED.calculation_method,
            source_periods = EXCLUDED.source_periods,
            source = EXCLUDED.source,
            updated_at = NOW()
        """
    )

    with engine.begin() as conn:
        conn.execute(sql, rows)

    return len(rows)


def build_ttm_for_company(
    company_id: int,
    statement_scope: str,
) -> int:
    """
    Build and persist all available TTM rows for one company/scope.
    """
    rows = calculate_ttm_for_company(
        company_id=company_id,
        statement_scope=statement_scope,
    )

    return _upsert_ttm_rows(rows)


def build_ttm_for_all(
    statement_scope: str | None = None,
) -> int:
    """
    Build and persist TTM rows company-by-company.

    Processing one company/scope at a time keeps memory usage bounded and
    preserves the existing TTM calculation and Original/Revision logic.
    """
    conditions = ["period_type = 'quarterly'"]
    params: dict[str, Any] = {}

    if statement_scope is not None:
        conditions.append("statement_scope = :statement_scope")
        params["statement_scope"] = statement_scope

    sql = f"""
        SELECT DISTINCT
            company_id,
            statement_scope
        FROM financial_statements
        WHERE {" AND ".join(conditions)}
        ORDER BY company_id, statement_scope
    """

    with engine.connect() as conn:
        company_scopes = conn.execute(
            text(sql),
            params,
        ).all()

    total = 0

    for company_id, scope in company_scopes:
        total += build_ttm_for_company(
            company_id=int(company_id),
            statement_scope=scope,
        )

    return total

def get_latest_ttm_as_of(
    company_id: int,
    statement_scope: str,
    as_of_date: date,
) -> dict[str, Any] | None:
    """
    Return the latest TTM row that was available as of `as_of_date`.

    A TTM row is eligible only when its latest_filing_date is on or
    before the requested as-of date. Among eligible rows, the latest
    period_end is selected.

    This prevents look-ahead bias in historical valuation/analysis.
    """
    sql = text(
        """
        SELECT
            id,
            company_id,
            period_end,
            latest_filing_date,
            statement_scope,
            revenue_ttm,
            ebitda_ttm,
            ebit_ttm,
            profit_before_tax_ttm,
            net_income_ttm,
            eps_ttm,
            operating_cash_flow_ttm,
            capital_expenditure_ttm,
            free_cash_flow_ttm,
            total_assets,
            total_equity,
            total_debt,
            cash_and_equivalents,
            calculation_method,
            source_periods,
            source
        FROM ttm_financials
        WHERE company_id = :company_id
          AND statement_scope = :statement_scope
          AND latest_filing_date <= :as_of_date
        ORDER BY period_end DESC
        LIMIT 1
        """
    )

    with engine.connect() as conn:
        row = conn.execute(
            sql,
            {
                "company_id": company_id,
                "statement_scope": statement_scope,
                "as_of_date": as_of_date,
            },
        ).mappings().first()

    return dict(row) if row is not None else None