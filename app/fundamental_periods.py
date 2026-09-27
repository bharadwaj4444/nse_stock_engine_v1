from __future__ import annotations

from datetime import date
from typing import Any


def find_yoy_previous(
    current: dict[str, Any],
    statements: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """
    Find the comparable prior-year statement.

    Quarterly:
        2026-06-30 -> 2025-06-30

    Annual:
        2026-03-31 -> 2025-03-31

    Statement scope and period type must match.
    """

    current_period_type = current["period_type"]
    current_period_end = current["period_end"]
    current_scope = current["statement_scope"]

    if current_period_type not in {"quarterly", "annual"}:
        return None

    target_year = current_period_end.year - 1

    candidates = [
        row
        for row in statements
        if row["period_type"] == current_period_type
        and row["statement_scope"] == current_scope
        and row["period_end"].month == current_period_end.month
        and row["period_end"].day == current_period_end.day
        and row["period_end"].year == target_year
    ]

    if not candidates:
        return None

    candidates.sort(
        key=lambda row: row["period_end"],
        reverse=True,
    )

    return candidates[0]


def _previous_quarter_end(period_end: date) -> date:
    """
    Return the expected immediately preceding Indian fiscal quarter end.

    Mar 31 -> Dec 31 previous year
    Jun 30 -> Mar 31 same year
    Sep 30 -> Jun 30 same year
    Dec 31 -> Sep 30 same year
    """

    quarter_ends = {
        (3, 31): (12, 31, -1),
        (6, 30): (3, 31, 0),
        (9, 30): (6, 30, 0),
        (12, 31): (9, 30, 0),
    }

    previous = quarter_ends.get(
        (period_end.month, period_end.day)
    )

    if previous is None:
        raise ValueError(
            f"Unsupported quarterly period end: {period_end}"
        )

    month, day, year_offset = previous

    return date(
        period_end.year + year_offset,
        month,
        day,
    )


def find_qoq_previous(
    current: dict[str, Any],
    statements: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """
    Find the exact immediately preceding comparable quarter.

    Only quarterly statements are considered.
    Statement scope must match.
    """

    if current["period_type"] != "quarterly":
        return None

    current_date = current["period_end"]
    current_scope = current["statement_scope"]

    target_date = _previous_quarter_end(current_date)

    candidates = [
        row
        for row in statements
        if row["period_type"] == "quarterly"
        and row["statement_scope"] == current_scope
        and row["period_end"] == target_date
    ]

    if not candidates:
        return None

    candidates.sort(
        key=lambda row: row["period_end"],
        reverse=True,
    )

    return candidates[0]
