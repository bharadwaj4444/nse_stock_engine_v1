from __future__ import annotations

from datetime import date

from app.core.types import Outcome


def resolve_outcome(
    company_id: int,
    trade_date: date,
    expected_return: float | None = None,
    actual_return: float | None = None,
) -> Outcome:
    """
    Resolve the verification outcome for a held instrument.

    The deviation is the gap between the expected return (from the
    historical backtest expectation for the instrument's decile) and the
    actual observed forward return over the hold horizon.
    """

    expected = None if expected_return is None else float(expected_return)
    actual = None if actual_return is None else float(actual_return)

    deviation = (
        expected - actual
        if expected is not None and actual is not None
        else None
    )

    status = (
        "verified"
        if deviation is not None
        else "pending"
    )

    return Outcome(
        company_id=company_id,
        trade_date=trade_date,
        expected_return=expected_return,
        actual_return=actual_return,
        deviation=deviation,
        status=status,
    )
