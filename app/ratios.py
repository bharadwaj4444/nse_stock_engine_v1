from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from typing import Any

from sqlalchemy import text

from app.db import engine


RATIO_FIELDS = (
    "ebitda_margin",
    "ebit_margin",
    "net_profit_margin",
    "roe",
    "roa",
    "revenue_growth_yoy",
    "ebitda_growth_yoy",
    "ebit_growth_yoy",
    "net_income_growth_yoy",
    "eps_growth_yoy",
    "debt_to_equity",
    "debt_to_ebitda",
    "net_debt_to_ebitda",
    "asset_turnover",
    "eps_ttm",
    "operating_cash_flow_margin",
    "free_cash_flow_margin",
    "fcf_to_net_income",
    "ocf_to_net_income",
)


def _ratio(
    numerator: Decimal | None,
    denominator: Decimal | None,
) -> Decimal | None:
    if numerator is None or denominator is None:
        return None

    if denominator == 0:
        return None

    return numerator / denominator


def _growth(
    current: Decimal | None,
    previous: Decimal | None,
) -> Decimal | None:
    if current is None or previous is None:
        return None

    if previous == 0:
        return None

    return (current - previous) / abs(previous)


def _build_ratio_row(
    current: dict[str, Any],
    previous: dict[str, Any] | None,
) -> dict[str, Any]:

    revenue = current["revenue_ttm"]
    ebitda = current["ebitda_ttm"]
    ebit = current["ebit_ttm"]
    net_income = current["net_income_ttm"]

    assets = current["total_assets"]
    equity = current["total_equity"]
    debt = current["total_debt"]
    cash = current["cash_and_equivalents"]

    row: dict[str, Any] = {
        "company_id": current["company_id"],
        "period_end": current["period_end"],
        "statement_scope": current["statement_scope"],

        "ebitda_margin": _ratio(ebitda, revenue),
        "ebit_margin": _ratio(ebit, revenue),
        "net_profit_margin": _ratio(net_income, revenue),

        "roe": _ratio(net_income, equity),
        "roa": _ratio(net_income, assets),

        "revenue_growth_yoy": None,
        "ebitda_growth_yoy": None,
        "ebit_growth_yoy": None,
        "net_income_growth_yoy": None,
        "eps_growth_yoy": None,

        "debt_to_equity": _ratio(debt, equity),
        "debt_to_ebitda": _ratio(debt, ebitda),

        "net_debt_to_ebitda": None,

        "asset_turnover": _ratio(revenue, assets),

        "eps_ttm": current["eps_ttm"],

        # Cash-flow ratios intentionally remain NULL until
        # quarterly cash-flow ingestion is available.
        "operating_cash_flow_margin": None,
        "free_cash_flow_margin": None,
        "fcf_to_net_income": None,
        "ocf_to_net_income": None,

        "calculation_method": "TTM_RATIOS",
        "source_period": current["period_end"],
        "prior_period": None if previous is None else previous["period_end"],
        "source": "DERIVED",
    }

    if debt is not None and cash is not None:
        net_debt = debt - cash
        row["net_debt_to_ebitda"] = _ratio(net_debt, ebitda)

    if previous is not None:
        row["revenue_growth_yoy"] = _growth(
            current["revenue_ttm"],
            previous["revenue_ttm"],
        )

        row["ebitda_growth_yoy"] = _growth(
            current["ebitda_ttm"],
            previous["ebitda_ttm"],
        )

        row["ebit_growth_yoy"] = _growth(
            current["ebit_ttm"],
            previous["ebit_ttm"],
        )

        row["net_income_growth_yoy"] = _growth(
            current["net_income_ttm"],
            previous["net_income_ttm"],
        )

        row["eps_growth_yoy"] = _growth(
            current["eps_ttm"],
            previous["eps_ttm"],
        )

    return row


def _load_ttm_rows(
    company_id: int | None = None,
    statement_scope: str | None = None,
) -> list[dict[str, Any]]:

    conditions = []
    params: dict[str, Any] = {}

    if company_id is not None:
        conditions.append("company_id = :company_id")
        params["company_id"] = company_id

    if statement_scope is not None:
        conditions.append("statement_scope = :statement_scope")
        params["statement_scope"] = statement_scope

    where = ""

    if conditions:
        where = "WHERE " + " AND ".join(conditions)

    sql = f"""
        SELECT
            company_id,
            period_end,
            statement_scope,

            revenue_ttm,
            ebitda_ttm,
            ebit_ttm,
            net_income_ttm,
            eps_ttm,

            total_assets,
            total_equity,
            total_debt,
            cash_and_equivalents

        FROM ttm_financials
        {where}
        ORDER BY
            company_id,
            statement_scope,
            period_end
    """

    with engine.connect() as conn:
        rows = conn.execute(text(sql), params).mappings().all()

    return [dict(row) for row in rows]


def calculate_ratios_for_company(
    company_id: int,
    statement_scope: str,
) -> list[dict[str, Any]]:

    rows = _load_ttm_rows(
        company_id=company_id,
        statement_scope=statement_scope,
    )

    rows.sort(key=lambda x: x["period_end"])

    result = []

    for index, current in enumerate(rows):

        previous = None

        # YoY requires the TTM period exactly 12 months earlier.
        if index > 0:
            candidate = rows[index - 1]

            if (
                candidate["period_end"].year
                == current["period_end"].year - 1
                and candidate["period_end"].month
                == current["period_end"].month
                and candidate["period_end"].day
                == current["period_end"].day
            ):
                previous = candidate

        result.append(
            _build_ratio_row(
                current,
                previous,
            )
        )

    return result


def _upsert_ratio_rows(rows: list[dict[str, Any]]) -> int:

    if not rows:
        return 0

    sql = text(
        """
        INSERT INTO financial_ratios (
            company_id,
            period_end,
            statement_scope,

            ebitda_margin,
            ebit_margin,
            net_profit_margin,
            roe,
            roa,

            revenue_growth_yoy,
            ebitda_growth_yoy,
            ebit_growth_yoy,
            net_income_growth_yoy,
            eps_growth_yoy,

            debt_to_equity,
            debt_to_ebitda,
            net_debt_to_ebitda,

            asset_turnover,
            eps_ttm,

            operating_cash_flow_margin,
            free_cash_flow_margin,
            fcf_to_net_income,
            ocf_to_net_income,

            calculation_method,
            source_period,
            prior_period,
            source,

            updated_at
        )
        VALUES (
            :company_id,
            :period_end,
            :statement_scope,

            :ebitda_margin,
            :ebit_margin,
            :net_profit_margin,
            :roe,
            :roa,

            :revenue_growth_yoy,
            :ebitda_growth_yoy,
            :ebit_growth_yoy,
            :net_income_growth_yoy,
            :eps_growth_yoy,

            :debt_to_equity,
            :debt_to_ebitda,
            :net_debt_to_ebitda,

            :asset_turnover,
            :eps_ttm,

            :operating_cash_flow_margin,
            :free_cash_flow_margin,
            :fcf_to_net_income,
            :ocf_to_net_income,

            :calculation_method,
            :source_period,
            :prior_period,
            :source,

            NOW()
        )
        ON CONFLICT (
            company_id,
            period_end,
            statement_scope
        )
        DO UPDATE SET

            ebitda_margin = EXCLUDED.ebitda_margin,
            ebit_margin = EXCLUDED.ebit_margin,
            net_profit_margin = EXCLUDED.net_profit_margin,
            roe = EXCLUDED.roe,
            roa = EXCLUDED.roa,

            revenue_growth_yoy = EXCLUDED.revenue_growth_yoy,
            ebitda_growth_yoy = EXCLUDED.ebitda_growth_yoy,
            ebit_growth_yoy = EXCLUDED.ebit_growth_yoy,
            net_income_growth_yoy = EXCLUDED.net_income_growth_yoy,
            eps_growth_yoy = EXCLUDED.eps_growth_yoy,

            debt_to_equity = EXCLUDED.debt_to_equity,
            debt_to_ebitda = EXCLUDED.debt_to_ebitda,
            net_debt_to_ebitda = EXCLUDED.net_debt_to_ebitda,

            asset_turnover = EXCLUDED.asset_turnover,
            eps_ttm = EXCLUDED.eps_ttm,

            operating_cash_flow_margin =
                EXCLUDED.operating_cash_flow_margin,

            free_cash_flow_margin =
                EXCLUDED.free_cash_flow_margin,

            fcf_to_net_income =
                EXCLUDED.fcf_to_net_income,

            ocf_to_net_income =
                EXCLUDED.ocf_to_net_income,

            calculation_method = EXCLUDED.calculation_method,
            source_period = EXCLUDED.source_period,
            prior_period = EXCLUDED.prior_period,
            source = EXCLUDED.source,
            updated_at = NOW()
        """
    )

    with engine.begin() as conn:
        conn.execute(sql, rows)

    return len(rows)


def build_ratios_for_company(
    company_id: int,
    statement_scope: str,
) -> int:

    rows = calculate_ratios_for_company(
        company_id,
        statement_scope,
    )

    return _upsert_ratio_rows(rows)


def build_ratios_for_all(
    statement_scope: str | None = None,
) -> int:

    rows = _load_ttm_rows(
        statement_scope=statement_scope,
    )

    grouped: dict[tuple[int, str], list[dict[str, Any]]] = defaultdict(list)

    for row in rows:
        key = (
            row["company_id"],
            row["statement_scope"],
        )
        grouped[key].append(row)

    output: list[dict[str, Any]] = []

    for group_rows in grouped.values():

        group_rows.sort(
            key=lambda x: x["period_end"]
        )

        for index, current in enumerate(group_rows):

            previous = None

            if index > 0:
                candidate = group_rows[index - 1]

                if (
                    candidate["period_end"].year
                    == current["period_end"].year - 1
                    and candidate["period_end"].month
                    == current["period_end"].month
                    and candidate["period_end"].day
                    == current["period_end"].day
                ):
                    previous = candidate

            output.append(
                _build_ratio_row(
                    current,
                    previous,
                )
            )

    return _upsert_ratio_rows(output)