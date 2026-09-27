from datetime import date

from app.sources.nse_financials import (
    NSEFinancialClient,
    FinancialFiling,
)


def test_parse_q1_financial_filing_uses_correct_context():
    fixture = (
        "tests/fixtures/reliance_2026q1_consolidated.xml"
    )

    with open(fixture, encoding="utf-8") as f:
        xml_text = f.read()

    filing = FinancialFiling(
        symbol="RELIANCE",
        company_name="Reliance Industries Limited",
        period_end=date(2026, 6, 30),
        submission_type="Original",
        audit_status="Un-Audited",
        statement_scope="Consolidated",
        details_url=None,
        xbrl_url="https://nsearchives.nseindia.com/"
        "corporate/xbrl/"
        "INTEGRATED_FILING_INDAS_1695741_17072026075004_WEB.xml",
        ixbrl_url=None,
        broadcast_datetime=None,
        revised_datetime=None,
        revision_remarks=None,
        source_reference="175608",
        raw={},
    )

    client = NSEFinancialClient()

    statements = client.parse_xbrl(
        xml_text=xml_text,
        filing=filing,
    )

    assert len(statements) == 1

    statement = statements[0]

    assert statement["period_type"] == "quarterly"
    assert statement["period_end"] == date(2026, 6, 30)

    assert statement["revenue"] == 3118500000000.0
    assert statement["profit_before_tax"] == 306300000000.0
    assert statement["net_income"] == 231960000000.0
    assert statement["eps"] == 15.48

    assert statement["operating_cash_flow"] is None
    assert statement["capital_expenditure"] is None
    assert statement["free_cash_flow"] is None

    assert statement["total_assets"] is None
    assert statement["total_equity"] is None
    assert statement["total_debt"] is None
    assert statement["cash_and_equivalents"] is None