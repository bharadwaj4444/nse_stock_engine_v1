from datetime import date

from app.ingest import derive_quarterly_financials


def make_statement(
    company_id,
    period_end,
    *,
    pnl_context_type="ytd",
    pnl_start="2025-04-01",
    cash_flow_start=None,
    cash_flow_end=None,
    ytd_start=None,
    ytd_end=None,
    ytd_ocf=None,
    ytd_capex=None,
    ocf=None,
    capex=None,
):
    return {
        "company_id": company_id,
        "statement_scope": "Standalone",
        "submission_type": "Original",
        "period_type": "quarterly",
        "period_end": date.fromisoformat(period_end),

        "operating_cash_flow": ocf,
        "capital_expenditure": capex,
        "free_cash_flow": None,

        "_ytd_operating_cash_flow": ytd_ocf,
        "_ytd_capital_expenditure": ytd_capex,
        "_ytd_start": ytd_start,
        "_ytd_end": ytd_end,

        "_cash_flow_start": cash_flow_start,
        "_cash_flow_end": cash_flow_end,

        "_pnl_context_type": pnl_context_type,
        "_pnl_start": pnl_start,
    }


def test_direct_quarter_cash_flow_without_ytd_values():
    statement = make_statement(
        1,
        "2026-09-30",
        pnl_context_type="quarter",
        pnl_start="2026-07-01",
        cash_flow_start="2026-07-01",
        cash_flow_end="2026-09-30",
        ocf=100,
        capex=20,
    )

    derive_quarterly_financials([statement])

    assert statement["operating_cash_flow"] == 100
    assert statement["capital_expenditure"] == 20
    assert statement["free_cash_flow"] == 80


def test_cumulative_cash_flow_uses_previous_ytd_statement():
    h1 = make_statement(
        1,
        "2025-09-30",
        ytd_start="2025-04-01",
        ytd_end="2025-09-30",
        ytd_ocf=144_640_000_000,
        ytd_capex=11_080_000_000,
    )

    nine_months = make_statement(
        1,
        "2025-12-31",
        ytd_start="2025-04-01",
        ytd_end="2025-12-31",
        ytd_ocf=203_930_000_000,
        ytd_capex=13_710_000_000,
    )

    derive_quarterly_financials([h1, nine_months])

    assert nine_months["operating_cash_flow"] == 59_290_000_000
    assert nine_months["capital_expenditure"] == 2_630_000_000
    assert nine_months["free_cash_flow"] == 56_660_000_000


def test_direct_q1_cash_flow_can_be_h1_cumulative_baseline():
    q1 = make_statement(
        1,
        "2025-06-30",
        pnl_context_type="quarter",
        pnl_start="2025-04-01",
        cash_flow_start="2025-04-01",
        cash_flow_end="2025-06-30",
        ocf=100,
        capex=10,
    )

    h1 = make_statement(
        1,
        "2025-09-30",
        ytd_start="2025-04-01",
        ytd_end="2025-09-30",
        ytd_ocf=250,
        ytd_capex=30,
    )

    derive_quarterly_financials([q1, h1])

    assert h1["operating_cash_flow"] == 150
    assert h1["capital_expenditure"] == 20
    assert h1["free_cash_flow"] == 130


def test_cash_flow_does_not_match_another_company():
    h1 = make_statement(
        1,
        "2025-09-30",
        ytd_start="2025-04-01",
        ytd_end="2025-09-30",
        ytd_ocf=100,
        ytd_capex=10,
    )

    nine_months = make_statement(
        2,
        "2025-12-31",
        ytd_start="2025-04-01",
        ytd_end="2025-12-31",
        ytd_ocf=250,
        ytd_capex=30,
    )

    derive_quarterly_financials([h1, nine_months])

    assert nine_months["operating_cash_flow"] is None
    assert nine_months["capital_expenditure"] is None
    assert nine_months["free_cash_flow"] is None