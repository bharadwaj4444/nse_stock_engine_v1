from datetime import date, datetime, timezone
from decimal import Decimal

from app.ingest import _capture_reported_values, derive_quarterly_financials
import uuid

import pytest
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError

from app.db import SessionLocal
from app.ingest import save_financial_statements
from app.models import (
    Company,
    FinancialRawFiling,
    FinancialStatement,
    FinancialStatementVersion,
    FinancialStatementVersionSource,
)


def test_snapshot_preserves_parser_values():
    statement = {
        "period_type": "quarterly",
        "period_end": date(2026, 6, 30),
        "revenue": Decimal("123456.7890"),
        "_pnl_context_type": "ytd",
        "_pnl_start": "2026-04-01",
        "_ytd_revenue": Decimal("123456.7890"),
        "company_id": 10,
        "_raw_filing_id": 200,
    }

    _capture_reported_values(statement)

    snapshot = statement["_reported_values"]

    assert snapshot["period_end"] == "2026-06-30"
    assert snapshot["revenue"] == "123456.7890"
    assert snapshot["_pnl_context_type"] == "ytd"
    assert snapshot["_pnl_start"] == "2026-04-01"
    assert snapshot["_ytd_revenue"] == "123456.7890"

    assert "company_id" not in snapshot
    assert "_raw_filing_id" not in snapshot


def test_snapshot_is_independent_of_later_derivation():
    statement = {
        "revenue": 1000.0,
        "_ytd_revenue": 1000.0,
    }

    _capture_reported_values(statement)

    statement["revenue"] = 400.0
    statement["_ytd_revenue"] = 1000.0

    assert statement["_reported_values"]["revenue"] == 1000.0


def test_snapshot_serializes_datetime_and_decimal():
    statement = {
        "filing_time": datetime(
            2026, 7, 17, 10, 30,
            tzinfo=timezone.utc,
        ),
        "amount": Decimal("987654321.123456"),
    }

    _capture_reported_values(statement)

    snapshot = statement["_reported_values"]

    assert snapshot["filing_time"] == "2026-07-17T10:30:00+00:00"
    assert snapshot["amount"] == "987654321.123456"


def _source_ids(statement):
    return {
        (
            item["source_raw_filing_id"],
            item["component"],
            item["source_role"],
            item["derivation_method"],
        )
        for item in statement.get("_derivation_sources", [])
    }


def test_quarterly_pnl_records_current_and_previous_filings():
    previous = {
        "company_id": 1,
        "_raw_filing_id": 100,
        "statement_scope": "Consolidated",
        "submission_type": "Original",
        "period_type": "quarterly",
        "period_end": date(2026, 6, 30),
        "_pnl_context_type": "ytd",
        "_pnl_start": "2026-04-01",
        "_ytd_revenue": 100,
        "_ytd_profit_before_tax": 20,
        "_ytd_net_income": 15,
    }

    current = {
        "company_id": 1,
        "_raw_filing_id": 200,
        "statement_scope": "Consolidated",
        "submission_type": "Original",
        "period_type": "quarterly",
        "period_end": date(2026, 9, 30),
        "_pnl_context_type": "ytd",
        "_pnl_start": "2026-04-01",
        "_ytd_revenue": 250,
        "_ytd_profit_before_tax": 50,
        "_ytd_net_income": 35,
    }

    derive_quarterly_financials([previous, current])

    assert current["revenue"] == 150
    assert _source_ids(current) == {
        (200, "PNL", "CURRENT_CUMULATIVE", "YTD_DIFFERENCE"),
        (100, "PNL", "PREVIOUS_CUMULATIVE", "YTD_DIFFERENCE"),
    }


def test_quarterly_cash_flow_records_direct_q1_baseline():
    q1 = {
        "company_id": 1,
        "_raw_filing_id": 300,
        "statement_scope": "Standalone",
        "submission_type": "Original",
        "period_type": "quarterly",
        "period_end": date(2026, 6, 30),
        "_pnl_context_type": "quarter",
        "_pnl_start": "2026-04-01",
        "_cash_flow_start": "2026-04-01",
        "_cash_flow_end": "2026-06-30",
        "operating_cash_flow": 100,
        "capital_expenditure": 10,
    }

    h1 = {
        "company_id": 1,
        "_raw_filing_id": 301,
        "statement_scope": "Standalone",
        "submission_type": "Original",
        "period_type": "quarterly",
        "period_end": date(2026, 9, 30),
        "_pnl_context_type": "ytd",
        "_pnl_start": "2026-04-01",
        "_ytd_start": "2026-04-01",
        "_ytd_end": "2026-09-30",
        "_ytd_operating_cash_flow": 250,
        "_ytd_capital_expenditure": 30,
    }

    derive_quarterly_financials([q1, h1])

    assert h1["operating_cash_flow"] == 150
    assert _source_ids(h1) == {
        (301, "CASH_FLOW", "CURRENT_CUMULATIVE", "YTD_DIFFERENCE"),
        (300, "CASH_FLOW", "PREVIOUS_CUMULATIVE", "YTD_DIFFERENCE"),
    }


def test_q4_pnl_records_q4_and_previous_filings():
    previous = {
        "company_id": 1,
        "_raw_filing_id": 400,
        "statement_scope": "Consolidated",
        "submission_type": "Original",
        "period_type": "quarterly",
        "period_end": date(2026, 12, 31),
        "_pnl_context_type": "ytd",
        "_pnl_start": "2026-04-01",
        "_ytd_start": "2026-04-01",
        "_ytd_revenue": 300,
        "_ytd_profit_before_tax": 60,
        "_ytd_net_income": 45,
    }

    q4 = {
        "company_id": 1,
        "_raw_filing_id": 401,
        "statement_scope": "Consolidated",
        "submission_type": "Original",
        "period_type": "quarterly",
        "period_end": date(2027, 3, 31),
        "_pnl_context_type": "ytd",
        "_pnl_start": "2026-04-01",
        "_ytd_revenue": 450,
        "_ytd_profit_before_tax": 90,
        "_ytd_net_income": 65,
    }

    annual = {
        "company_id": 1,
        "_raw_filing_id": 402,
        "statement_scope": "Consolidated",
        "submission_type": "Original",
        "period_type": "annual",
        "period_end": date(2027, 3, 31),
        "_pnl_start": "2026-04-01",
    }

    derive_quarterly_financials([previous, q4, annual])

    assert q4["revenue"] == 150
    assert _source_ids(q4) == {
        (401, "PNL", "CURRENT_CUMULATIVE", "YTD_DIFFERENCE"),
        (400, "PNL", "PREVIOUS_CUMULATIVE", "YTD_DIFFERENCE"),
    }


def test_q4_cash_flow_records_annual_and_previous_filings():
    previous = {
        "company_id": 1,
        "_raw_filing_id": 500,
        "statement_scope": "Standalone",
        "submission_type": "Original",
        "period_type": "quarterly",
        "period_end": date(2026, 12, 31),
        "_ytd_start": "2026-04-01",
        "_ytd_end": "2026-12-31",
        "_ytd_operating_cash_flow": 300,
        "_ytd_capital_expenditure": 30,
    }

    q4 = {
        "company_id": 1,
        "_raw_filing_id": 501,
        "statement_scope": "Standalone",
        "submission_type": "Original",
        "period_type": "quarterly",
        "period_end": date(2027, 3, 31),
    }

    annual = {
        "company_id": 1,
        "_raw_filing_id": 502,
        "statement_scope": "Standalone",
        "submission_type": "Original",
        "period_type": "annual",
        "period_end": date(2027, 3, 31),
        "_cash_flow_start": "2026-04-01",
        "_cash_flow_end": "2027-03-31",
        "operating_cash_flow": 450,
        "capital_expenditure": 50,
    }

    derive_quarterly_financials([previous, q4, annual])

    assert q4["operating_cash_flow"] == 150
    assert q4["capital_expenditure"] == 20
    assert _source_ids(q4) == {
        (502, "CASH_FLOW", "ANNUAL_TOTAL", "ANNUAL_MINUS_YTD"),
        (500, "CASH_FLOW", "PREVIOUS_CUMULATIVE", "ANNUAL_MINUS_YTD"),
    }


def test_partial_cash_flow_records_only_available_component_inputs():
    previous = {
        "company_id": 1,
        "_raw_filing_id": 600,
        "statement_scope": "Standalone",
        "submission_type": "Original",
        "period_type": "quarterly",
        "period_end": date(2026, 6, 30),
        "_ytd_start": "2026-04-01",
        "_ytd_end": "2026-06-30",
        "_ytd_operating_cash_flow": 100,
        "_ytd_capital_expenditure": None,
    }

    current = {
        "company_id": 1,
        "_raw_filing_id": 601,
        "statement_scope": "Standalone",
        "submission_type": "Original",
        "period_type": "quarterly",
        "period_end": date(2026, 9, 30),
        "_ytd_start": "2026-04-01",
        "_ytd_end": "2026-09-30",
        "_ytd_operating_cash_flow": 250,
        "_ytd_capital_expenditure": 30,
    }

    derive_quarterly_financials([previous, current])

    assert current["operating_cash_flow"] == 150
    assert current.get("capital_expenditure") is None
    assert _source_ids(current) == {
        (601, "CASH_FLOW", "CURRENT_CUMULATIVE", "YTD_DIFFERENCE"),
        (600, "CASH_FLOW", "PREVIOUS_CUMULATIVE", "YTD_DIFFERENCE"),
    }


def test_missing_cash_flow_baseline_records_no_lineage():
    current = {
        "company_id": 1,
        "_raw_filing_id": 700,
        "statement_scope": "Standalone",
        "submission_type": "Original",
        "period_type": "quarterly",
        "period_end": date(2026, 9, 30),
        "_ytd_start": "2026-04-01",
        "_ytd_end": "2026-09-30",
        "_ytd_operating_cash_flow": 250,
        "_ytd_capital_expenditure": 30,
    }

    derive_quarterly_financials([current])

    assert current.get("operating_cash_flow") is None
    assert current.get("_derivation_sources", []) == []

def _create_test_company_and_filings():
    symbol = f"TEST_VERSION_{uuid.uuid4().hex[:12].upper()}"

    with SessionLocal.begin() as db:
        company = Company(
            nse_symbol=symbol,
            company_name="Financial Version Test Company",
            status="TEST",
            is_active=False,
        )
        db.add(company)
        db.flush()

        company_id = company.id

        filings = []

        for index in range(3):
            filing = FinancialRawFiling(
                company_id=company_id,
                symbol=symbol,
                period_end=date(2026, 9, 30),
                filing_date=date(2026, 10, 20 + index),
                statement_scope="Consolidated",
                submission_type="Original",
                source_reference=f"TEST-{uuid.uuid4().hex}",
                raw_relative_path=f"test/{uuid.uuid4().hex}.xml",
                sha256=uuid.uuid4().hex + uuid.uuid4().hex,
                file_size=100,
                processing_status="PROCESSED",
            )
            db.add(filing)
            filings.append(filing)

        db.flush()
        filing_ids = [filing.id for filing in filings]

    return company_id, filing_ids


def _financial_statement_row(
    company_id,
    raw_filing_id,
    revenue,
    derivation_sources=None,
):
    return {
        "company_id": company_id,
        "_raw_filing_id": raw_filing_id,
        "_reported_values": {
            "revenue": str(revenue),
            "parser_version": "test",
        },
        "_derivation_sources": derivation_sources or [],
        "period_type": "quarterly",
        "period_end": date(2026, 9, 30),
        "filing_date": date(2026, 10, 20),
        "revenue": revenue,
        "source": "NSE_XBRL",
        "source_reference": f"TEST-{raw_filing_id}",
        "statement_scope": "Consolidated",
        "submission_type": "Original",
    }


def _cleanup_test_company(company_id, filing_ids):
    with SessionLocal.begin() as db:
        db.execute(
            delete(FinancialStatementVersionSource).where(
                FinancialStatementVersionSource.source_raw_filing_id.in_(
                    filing_ids
                )
            )
        )

        db.execute(
            delete(FinancialStatementVersion).where(
                FinancialStatementVersion.raw_filing_id.in_(filing_ids)
            )
        )

        db.execute(
            delete(FinancialStatement).where(
                FinancialStatement.company_id == company_id
            )
        )

        db.execute(
            delete(FinancialRawFiling).where(
                FinancialRawFiling.id.in_(filing_ids)
            )
        )

        db.execute(
            delete(Company).where(Company.id == company_id)
        )

def test_financial_statement_version_persistence_and_lineage():
    company_id, filing_ids = _create_test_company_and_filings()
    first_filing, second_filing, third_filing = filing_ids

    try:
        # Initial insert: first filing, with second filing as a dependency.
        row = _financial_statement_row(
            company_id,
            first_filing,
            1000,
            [
                {
                    "source_raw_filing_id": second_filing,
                    "component": "PNL",
                    "source_role": "PREVIOUS_CUMULATIVE",
                    "derivation_method": "YTD_DIFFERENCE",
                }
            ],
        )

        assert save_financial_statements([row]) == 1

        with SessionLocal() as db:
            versions = db.execute(
                select(FinancialStatementVersion).where(
                    FinancialStatementVersion.raw_filing_id == first_filing
                )
            ).scalars().all()

            assert len(versions) == 1
            version_id = versions[0].id
            assert versions[0].revenue == 1000
            assert versions[0].reported_values["revenue"] == "1000"

            lineage = db.execute(
                select(FinancialStatementVersionSource).where(
                    FinancialStatementVersionSource.version_id == version_id
                )
            ).scalars().all()

            assert len(lineage) == 1
            assert lineage[0].source_raw_filing_id == second_filing

        # Reprocess the same filing with changed values and changed lineage.
        updated_row = _financial_statement_row(
            company_id,
            first_filing,
            1200,
            [
                {
                    "source_raw_filing_id": first_filing,
                    "component": "PNL",
                    "source_role": "CURRENT_CUMULATIVE",
                    "derivation_method": "YTD_DIFFERENCE",
                }
            ],
        )

        assert save_financial_statements([updated_row]) == 1

        with SessionLocal() as db:
            versions = db.execute(
                select(FinancialStatementVersion).where(
                    FinancialStatementVersion.raw_filing_id == first_filing
                )
            ).scalars().all()

            assert len(versions) == 1
            assert versions[0].id == version_id
            assert versions[0].revenue == 1200
            assert versions[0].reported_values["revenue"] == "1200"

            lineage = db.execute(
                select(FinancialStatementVersionSource).where(
                    FinancialStatementVersionSource.version_id == version_id
                )
            ).scalars().all()

            assert len(lineage) == 1
            assert lineage[0].source_raw_filing_id == first_filing
            assert lineage[0].source_role == "CURRENT_CUMULATIVE"

        # A different raw filing for the same company and period
        # must create a separate version.
        revision_row = _financial_statement_row(
            company_id,
            third_filing,
            1500,
        )

        assert save_financial_statements([revision_row]) == 1

        with SessionLocal() as db:
            versions = db.execute(
                select(FinancialStatementVersion)
                .where(
                    FinancialStatementVersion.company_id == company_id,
                    FinancialStatementVersion.period_end == date(2026, 9, 30),
                )
                .order_by(FinancialStatementVersion.raw_filing_id)
            ).scalars().all()

            assert len(versions) == 2
            assert {version.raw_filing_id for version in versions} == {
                first_filing,
                third_filing,
            }

            # Legacy table remains one row for its existing identity.
            legacy_rows = db.execute(
                select(FinancialStatement).where(
                    FinancialStatement.company_id == company_id,
                    FinancialStatement.period_end == date(2026, 9, 30),
                )
            ).scalars().all()

            assert len(legacy_rows) == 1

    finally:
        _cleanup_test_company(company_id, filing_ids)

def test_financial_statement_version_failure_rolls_back_legacy_write():
    company_id, filing_ids = _create_test_company_and_filings()
    first_filing = filing_ids[0]

    invalid_row = _financial_statement_row(
        company_id,
        first_filing,
        2000,
        [
            {
                "source_raw_filing_id": 999999999999999,
                "component": "PNL",
                "source_role": "PREVIOUS_CUMULATIVE",
                "derivation_method": "YTD_DIFFERENCE",
            }
        ],
    )

    try:
        with pytest.raises(IntegrityError):
            save_financial_statements([invalid_row])

        with SessionLocal() as db:
            legacy_rows = db.execute(
                select(FinancialStatement).where(
                    FinancialStatement.company_id == company_id,
                    FinancialStatement.period_end == date(2026, 9, 30),
                )
            ).scalars().all()

            versions = db.execute(
                select(FinancialStatementVersion).where(
                    FinancialStatementVersion.raw_filing_id == first_filing
                )
            ).scalars().all()

            assert legacy_rows == []
            assert versions == []

    finally:
        _cleanup_test_company(company_id, filing_ids)