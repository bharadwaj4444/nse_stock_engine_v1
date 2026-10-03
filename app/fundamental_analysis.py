from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import select

from app.db import SessionLocal
from app.fundamental_periods import find_qoq_previous, find_yoy_previous
from app.fundamentals import calculate_fundamental_metrics
from app.models import Company, FinancialStatement
from app.ttm import get_latest_ttm_as_of

def _statement_dict(row: FinancialStatement) -> dict[str, Any]:
    return {
        "id": row.id,
        "company_id": row.company_id,
        "period_type": row.period_type,
        "period_end": row.period_end,
        "filing_date": row.filing_date,
        "revenue": row.revenue,
        "ebitda": row.ebitda,
        "ebit": row.ebit,
        "profit_before_tax": row.profit_before_tax,
        "net_income": row.net_income,
        "eps": row.eps,
        "total_assets": row.total_assets,
        "total_equity": row.total_equity,
        "total_debt": row.total_debt,
        "cash_and_equivalents": row.cash_and_equivalents,
        "operating_cash_flow": row.operating_cash_flow,
        "capital_expenditure": row.capital_expenditure,
        "free_cash_flow": row.free_cash_flow,
        "source": row.source,
        "source_reference": row.source_reference,
        "statement_scope": row.statement_scope,
        "submission_type": row.submission_type,
        "audit_status": row.audit_status,
        "reporting_standard": row.reporting_standard,
        "source_url": row.source_url,
    }

def _ttm_dict(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "company_id": row["company_id"],
        "period_end": row["period_end"],
        "filing_date": row["latest_filing_date"],
        "revenue": row["revenue_ttm"],
        "ebitda": row["ebitda_ttm"],
        "ebit": row["ebit_ttm"],
        "profit_before_tax": row["profit_before_tax_ttm"],
        "net_income": row["net_income_ttm"],
        "eps": row["eps_ttm"],
        "total_assets": row["total_assets"],
        "total_equity": row["total_equity"],
        "total_debt": row["total_debt"],
        "cash_and_equivalents": row["cash_and_equivalents"],
        "operating_cash_flow": row["operating_cash_flow_ttm"],
        "capital_expenditure": row["capital_expenditure_ttm"],
        "free_cash_flow": row["free_cash_flow_ttm"],
        "statement_scope": row["statement_scope"],
        "source": row["source"],
    }

def _current_metrics(
    current: dict[str, Any],
) -> dict[str, Any]:
    metrics = calculate_fundamental_metrics(current)

    return {
        "ebitda_margin": metrics["ebitda_margin"],
        "ebit_margin": metrics["ebit_margin"],
        "net_margin": metrics["net_margin"],
        "debt_to_equity": metrics["debt_to_equity"],
        "roe": metrics["roe"],
        "fcf_margin": metrics["fcf_margin"],
    }


def _comparison_metrics(
    current: dict[str, Any],
    previous: dict[str, Any] | None,
) -> dict[str, Any]:
    if previous is None:
        return {
            "period_end": None,
            "revenue_growth": None,
            "eps_growth": None,
            "fcf_growth": None,
        }

    metrics = calculate_fundamental_metrics(
        current,
        previous,
    )

    return {
        "period_end": previous["period_end"],
        "revenue_growth": metrics["revenue_growth"],
        "eps_growth": metrics["eps_growth"],
        "fcf_growth": metrics["fcf_growth"],
    }


def get_fundamental_analysis(
    symbol: str,
    period_end: date | None = None,
    period_type: str = "quarterly",
    statement_scope: str = "Consolidated",
    as_of_date: date | None = None,
) -> dict[str, Any]:
    """
    Calculate fundamental analysis for a company statement.

    Separates:
        current = current-period ratios
        yoy     = growth versus same period one year earlier
        qoq     = growth versus immediately preceding quarter
    """

    with SessionLocal() as session:
        company = session.scalar(
            select(Company).where(
                Company.nse_symbol == symbol.upper()
            )
        )

        if company is None:
            raise ValueError(
                f"Company not found: {symbol.upper()}"
            )
        
        conditions = [
            FinancialStatement.company_id == company.id,
            FinancialStatement.period_type == period_type,
            FinancialStatement.statement_scope == statement_scope,
        ]

        if period_end is not None:
            conditions.append(
                FinancialStatement.period_end == period_end
            )

        if as_of_date is not None:
            conditions.append(
                FinancialStatement.filing_date <= as_of_date
            )

        query = (
            select(FinancialStatement)
            .where(*conditions)
            .order_by(
                FinancialStatement.period_end.desc(),
                FinancialStatement.filing_date.desc(),
                FinancialStatement.id.desc(),
            )
        )

        current_row = session.scalars(query).first()

        if current_row is None:
            raise ValueError(
                f"No {statement_scope} {period_type} financial statement "
                f"found for {symbol.upper()}"
                + (
                    f" at {period_end}"
                    if period_end is not None
                    else ""
                )
            )

        history_conditions = [
            FinancialStatement.company_id == company.id,
            FinancialStatement.period_type == period_type,
            FinancialStatement.statement_scope == statement_scope,
        ]

        ttm_row = None

        if as_of_date is not None:
            history_conditions.append(
                FinancialStatement.filing_date <= as_of_date
            )
            ttm_row = get_latest_ttm_as_of(
                    company_id=company.id,
                    statement_scope=statement_scope,
                    as_of_date=as_of_date,
                )
        

        all_rows = list(
            session.scalars(
                select(FinancialStatement)
                .where(*history_conditions)
                .order_by(
                    FinancialStatement.period_end,
                    FinancialStatement.filing_date,
                    FinancialStatement.id,
                )
            )
        )

        company_data = {
            "id": company.id,
            "symbol": company.nse_symbol,
            "name": company.company_name,
        }

    current = _statement_dict(current_row)

    ttm = _ttm_dict(ttm_row) if ttm_row is not None else None

    statements = [_statement_dict(row) for row in all_rows]

    yoy_previous = find_yoy_previous(
        current,
        statements,
    )

    qoq_previous = find_qoq_previous(
        current,
        statements,
    )

    return {
        "company": company_data,
        "current": {
            "period_end": current["period_end"],
            "period_type": current["period_type"],
            "filing_date": current["filing_date"],
            "statement_scope": current["statement_scope"],
            "revenue": current["revenue"],
            "ebitda": current["ebitda"],
            "ebit": current["ebit"],
            "profit_before_tax": current["profit_before_tax"],
            "net_income": current["net_income"],
            "eps": current["eps"],
            "total_assets": current["total_assets"],
            "total_equity": current["total_equity"],
            "total_debt": current["total_debt"],
            "cash_and_equivalents": current["cash_and_equivalents"],
            "operating_cash_flow": current["operating_cash_flow"],
            "capital_expenditure": current["capital_expenditure"],
            "free_cash_flow": current["free_cash_flow"],
            "metrics": _current_metrics(current),
        },
        "yoy": _comparison_metrics(
            current,
            yoy_previous,
        ),
        "qoq": _comparison_metrics(
            current,
            qoq_previous,
        ),
        "ttm": (
            {
                "period_end": ttm["period_end"],
                "filing_date": ttm["filing_date"],
                "statement_scope": ttm["statement_scope"],
                "revenue": ttm["revenue"],
                "ebitda": ttm["ebitda"],
                "ebit": ttm["ebit"],
                "profit_before_tax": ttm["profit_before_tax"],
                "net_income": ttm["net_income"],
                "eps": ttm["eps"],
                "total_assets": ttm["total_assets"],
                "total_equity": ttm["total_equity"],
                "total_debt": ttm["total_debt"],
                "cash_and_equivalents": ttm["cash_and_equivalents"],
                "operating_cash_flow": ttm["operating_cash_flow"],
                "capital_expenditure": ttm["capital_expenditure"],
                "free_cash_flow": ttm["free_cash_flow"],
                "metrics": _current_metrics(ttm),
            }
            if ttm is not None
            else None
        ),
    }

def get_fundamental_history(
    symbol: str,
    period_type: str = "quarterly",
    statement_scope: str = "Consolidated",
) -> dict[str, Any]:
    with SessionLocal() as session:
        company = session.scalar(
            select(Company).where(
                Company.nse_symbol == symbol.upper()
            )
        )

        if company is None:
            raise ValueError(f"Company not found: {symbol.upper()}")

        rows = list(
            session.scalars(
                select(FinancialStatement)
                .where(
                    FinancialStatement.company_id == company.id,
                    FinancialStatement.period_type == period_type,
                    FinancialStatement.statement_scope == statement_scope,
                )
                .order_by(FinancialStatement.period_end)
            )
        )

    statements = [_statement_dict(row) for row in rows]

    history = []

    for current in statements:
        yoy_previous = find_yoy_previous(current, statements)
        qoq_previous = find_qoq_previous(current, statements)

        current_metrics = calculate_fundamental_metrics(current)

        yoy_metrics = calculate_fundamental_metrics(
            current,
            yoy_previous,
        ) if yoy_previous else None

        qoq_metrics = calculate_fundamental_metrics(
            current,
            qoq_previous,
        ) if qoq_previous else None

        history.append(
            {
                "period_end": current["period_end"],
                "period_type": current["period_type"],
                "statement_scope": current["statement_scope"],

                "revenue": current["revenue"],
                "ebitda": current["ebitda"],
                "ebit": current["ebit"],
                "profit_before_tax": current["profit_before_tax"],
                "net_income": current["net_income"],
                "eps": current["eps"],

                "total_assets": current["total_assets"],
                "total_equity": current["total_equity"],
                "total_debt": current["total_debt"],
                "cash_and_equivalents": current["cash_and_equivalents"],

                "operating_cash_flow": current["operating_cash_flow"],
                "capital_expenditure": current["capital_expenditure"],
                "free_cash_flow": current["free_cash_flow"],

                "metrics": {
                    "ebitda_margin": current_metrics["ebitda_margin"],
                    "ebit_margin": current_metrics["ebit_margin"],
                    "net_margin": current_metrics["net_margin"],
                    "debt_to_equity": current_metrics["debt_to_equity"],
                    "roe": current_metrics["roe"],
                    "fcf_margin": current_metrics["fcf_margin"],
                },

                "yoy": {
                    "period_end": (
                        yoy_previous["period_end"]
                        if yoy_previous
                        else None
                    ),
                    "revenue_growth": (
                        yoy_metrics["revenue_growth"]
                        if yoy_metrics
                        else None
                    ),
                    "eps_growth": (
                        yoy_metrics["eps_growth"]
                        if yoy_metrics
                        else None
                    ),
                    "fcf_growth": (
                        yoy_metrics["fcf_growth"]
                        if yoy_metrics
                        else None
                    ),
                },

                "qoq": {
                    "period_end": (
                        qoq_previous["period_end"]
                        if qoq_previous
                        else None
                    ),
                    "revenue_growth": (
                        qoq_metrics["revenue_growth"]
                        if qoq_metrics
                        else None
                    ),
                    "eps_growth": (
                        qoq_metrics["eps_growth"]
                        if qoq_metrics
                        else None
                    ),
                    "fcf_growth": (
                        qoq_metrics["fcf_growth"]
                        if qoq_metrics
                        else None
                    ),
                },
            }
        )

    return {
        "company": {
            "id": company.id,
            "symbol": company.nse_symbol,
            "name": company.company_name,
        },
        "period_type": period_type,
        "statement_scope": statement_scope,
        "count": len(history),
        "history": history,
    }