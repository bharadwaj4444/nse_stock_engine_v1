from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from typing import Any


Number = int | float | Decimal


def _value(row: Mapping[str, Any], key: str) -> Number | None:
    value = row.get(key)

    if value is None:
        return None

    try:
        return Decimal(str(value))
    except (ValueError, TypeError):
        return None


def _divide(
    numerator: Number | None,
    denominator: Number | None,
) -> Decimal | None:
    if numerator is None or denominator is None:
        return None

    denominator = Decimal(str(denominator))

    if denominator == 0:
        return None

    return Decimal(str(numerator)) / denominator


def _growth(
    current: Number | None,
    previous: Number | None,
) -> Decimal | None:
    if current is None or previous is None:
        return None

    previous = Decimal(str(previous))

    if previous == 0:
        return None

    return (
        Decimal(str(current)) - previous
    ) / abs(previous)


def calculate_fundamental_metrics(
    current: Mapping[str, Any],
    previous: Mapping[str, Any] | None = None,
) -> dict[str, Decimal | None]:
    """
    Calculate fundamental metrics for one financial statement.

    `current` and `previous` must represent the same period type
    and comparable statement scope.

    Growth metrics are calculated only when a comparable previous
    statement is supplied.
    """

    revenue = _value(current, "revenue")
    ebitda = _value(current, "ebitda")
    ebit = _value(current, "ebit")
    net_income = _value(current, "net_income")
    eps = _value(current, "eps")
    debt = _value(current, "total_debt")
    equity = _value(current, "total_equity")
    free_cash_flow = _value(current, "free_cash_flow")

    metrics: dict[str, Decimal | None] = {
        "revenue_growth": None,
        "ebitda_margin": _divide(ebitda, revenue),
        "ebit_margin": _divide(ebit, revenue),
        "net_margin": _divide(net_income, revenue),
        "eps_growth": None,
        "debt_to_equity": _divide(debt, equity),
        "roe": _divide(net_income, equity),
        "fcf_margin": _divide(free_cash_flow, revenue),
        "fcf_growth": None,
    }

    if previous is not None:
        metrics["revenue_growth"] = _growth(
            revenue,
            _value(previous, "revenue"),
        )

        metrics["eps_growth"] = _growth(
            eps,
            _value(previous, "eps"),
        )

        metrics["fcf_growth"] = _growth(
            free_cash_flow,
            _value(previous, "free_cash_flow"),
        )

    return metrics
