from datetime import date

from app.fundamental_periods import (
    find_qoq_previous,
    find_yoy_previous,
)


def statement(
    period_type: str,
    period_end: date,
    scope: str = "Consolidated",
) -> dict:
    return {
        "period_type": period_type,
        "period_end": period_end,
        "statement_scope": scope,
    }


def test_find_yoy_previous_quarter():
    current = statement(
        "quarterly",
        date(2026, 6, 30),
    )

    statements = [
        statement("quarterly", date(2025, 6, 30)),
        statement("quarterly", date(2026, 3, 31)),
        statement("quarterly", date(2025, 3, 31)),
    ]

    previous = find_yoy_previous(current, statements)

    assert previous is not None
    assert previous["period_end"] == date(2025, 6, 30)


def test_find_yoy_requires_same_scope():
    current = statement(
        "quarterly",
        date(2026, 6, 30),
        "Consolidated",
    )

    statements = [
        statement(
            "quarterly",
            date(2025, 6, 30),
            "Standalone",
        ),
    ]

    assert find_yoy_previous(current, statements) is None


def test_find_qoq_previous_quarter():
    current = statement(
        "quarterly",
        date(2026, 6, 30),
    )

    statements = [
        statement("quarterly", date(2026, 3, 31)),
        statement("quarterly", date(2025, 12, 31)),
        statement("quarterly", date(2026, 6, 30)),
    ]

    previous = find_qoq_previous(current, statements)

    assert previous is not None
    assert previous["period_end"] == date(2026, 3, 31)


def test_qoq_does_not_compare_annual():
    current = statement(
        "quarterly",
        date(2026, 6, 30),
    )

    statements = [
        statement("annual", date(2026, 3, 31)),
    ]

    assert find_qoq_previous(current, statements) is None

def test_qoq_returns_none_when_exact_previous_quarter_missing():
    current = statement(
        "quarterly",
        date(2026, 6, 30),
    )

    statements = [
        statement("quarterly", date(2025, 12, 31)),
    ]

    assert find_qoq_previous(current, statements) is None
