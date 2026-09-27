from decimal import Decimal

from app.fundamentals import calculate_fundamental_metrics


def test_fundamental_metrics():
    current = {
        "revenue": 200,
        "ebitda": 50,
        "ebit": 40,
        "net_income": 30,
        "eps": 15,
        "total_debt": 100,
        "total_equity": 200,
        "free_cash_flow": 20,
    }

    previous = {
        "revenue": 160,
        "eps": 10,
        "free_cash_flow": 10,
    }

    metrics = calculate_fundamental_metrics(
        current=current,
        previous=previous,
    )

    assert metrics["revenue_growth"] == Decimal("0.25")
    assert metrics["ebitda_margin"] == Decimal("0.25")
    assert metrics["ebit_margin"] == Decimal("0.20")
    assert metrics["net_margin"] == Decimal("0.15")
    assert metrics["eps_growth"] == Decimal("0.5")
    assert metrics["debt_to_equity"] == Decimal("0.5")
    assert metrics["roe"] == Decimal("0.15")
    assert metrics["fcf_margin"] == Decimal("0.10")
    assert metrics["fcf_growth"] == Decimal("1")


def test_missing_values_return_none():
    current = {
        "revenue": 100,
        "ebitda": None,
        "ebit": None,
        "net_income": 10,
        "eps": 5,
        "total_debt": None,
        "total_equity": None,
        "free_cash_flow": None,
    }

    previous = {
        "revenue": 90,
        "eps": 4,
        "free_cash_flow": None,
    }

    metrics = calculate_fundamental_metrics(
        current=current,
        previous=previous,
    )

    assert metrics["revenue_growth"] == Decimal("0.1111111111111111111111111111")
    assert metrics["ebitda_margin"] is None
    assert metrics["ebit_margin"] is None
    assert metrics["net_margin"] == Decimal("0.1")
    assert metrics["eps_growth"] == Decimal("0.25")
    assert metrics["debt_to_equity"] is None
    assert metrics["roe"] is None
    assert metrics["fcf_margin"] is None
    assert metrics["fcf_growth"] is None


def test_zero_denominator_returns_none():
    current = {
        "revenue": 0,
        "ebitda": 10,
        "ebit": 10,
        "net_income": 10,
        "eps": 5,
        "total_debt": 10,
        "total_equity": 0,
        "free_cash_flow": 10,
    }

    previous = {
        "revenue": 0,
        "eps": 0,
        "free_cash_flow": 0,
    }

    metrics = calculate_fundamental_metrics(
        current=current,
        previous=previous,
    )

    assert metrics["revenue_growth"] is None
    assert metrics["ebitda_margin"] is None
    assert metrics["ebit_margin"] is None
    assert metrics["net_margin"] is None
    assert metrics["eps_growth"] is None
    assert metrics["debt_to_equity"] is None
    assert metrics["roe"] is None
    assert metrics["fcf_margin"] is None
    assert metrics["fcf_growth"] is None
