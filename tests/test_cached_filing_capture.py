from __future__ import annotations

from datetime import date
import uuid

import pytest
from sqlalchemy import delete, select

import app.ingest as ingest
from app.db import SessionLocal
from app.models import (
    Company,
    FinancialRawFiling,
    FinancialStatement,
    FinancialStatementVersion,
    FinancialStatementVersionSource,
)

_SYMBOL = f"TEST_PITCORE_{uuid.uuid4().hex[:10].upper()}"

_A_STATEMENT = {
    "period_type": "quarterly",
    "period_end": date(2025, 9, 30),
    "statement_scope": "Standalone",
    "submission_type": "Original",
    "period_type_source": "ORIGINAL",
    "_pnl_context_type": "ytd",
    "_pnl_start": "2025-04-01",
    "_ytd_start": "2025-04-01",
    "_ytd_end": "2025-09-30",
    "_ytd_operating_cash_flow": 100_000_000,
    "_ytd_capital_expenditure": 10_000_000,
    "_ytd_revenue": 1_000_000_000,
    "revenue": None,
    "operating_cash_flow": None,
    "capital_expenditure": None,
    "filing_date": date(2025, 10, 20),
    "source": "NSE_XBRL",
    "source_reference": "TEST-A",
}

_B_STATEMENT = {
    "period_type": "quarterly",
    "period_end": date(2025, 12, 31),
    "statement_scope": "Standalone",
    "submission_type": "Original",
    "period_type_source": "ORIGINAL",
    "_pnl_context_type": "ytd",
    "_pnl_start": "2025-04-01",
    "_ytd_start": "2025-04-01",
    "_ytd_end": "2025-12-31",
    "_ytd_operating_cash_flow": 240_000_000,
    "_ytd_capital_expenditure": 30_000_000,
    "_ytd_revenue": 2_400_000_000,
    "revenue": None,
    "operating_cash_flow": None,
    "capital_expenditure": None,
    "filing_date": date(2026, 1, 20),
    "source": "NSE_XBRL",
    "source_reference": "TEST-B",
}


class _FakeNSEFinancialClient:
    # Parser stand-in: the wiring under test (capture -> derivation ->
    # persistence) does not depend on real XBRL parsing.
    def parse_xbrl(self, xml_text, filing, effective_filing_date):
        if xml_text == "statement-A":
            return [dict(_A_STATEMENT)]
        if xml_text == "statement-B":
            return [dict(_B_STATEMENT)]
        return []


def _seed_filings():
    with SessionLocal.begin() as db:
        company = Company(
            nse_symbol=_SYMBOL,
            company_name="Cached Filing Capture Test Company",
            status="TEST",
            is_active=False,
        )
        db.add(company)
        db.flush()
        company_id = company.id

        filings = []

        for label, period_end, filing_date in (
            ("a", date(2025, 9, 30), date(2025, 10, 20)),
            ("b", date(2025, 12, 31), date(2026, 1, 20)),
        ):
            filing = FinancialRawFiling(
                company_id=company_id,
                symbol=_SYMBOL,
                period_end=period_end,
                filing_date=filing_date,
                statement_scope="Standalone",
                submission_type="Original",
                source_reference=f"TEST-{label.upper()}",
                raw_relative_path=f"test/{label}.xml",
                sha256=uuid.uuid4().hex + uuid.uuid4().hex,
                file_size=100,
                processing_status="PENDING",
            )
            db.add(filing)
            filings.append(filing)

        db.flush()
        filing_ids = [filing.id for filing in filings]

    return company_id, filing_ids


def _cleanup(company_id, filing_ids):
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


def test_cached_processing_captures_parser_values_before_derivation(
    tmp_path,
    monkeypatch,
):
    company_id, filing_ids = _seed_filings()
    filing_a_id, filing_b_id = filing_ids

    raw_dir = tmp_path / "financial_xbrl"
    raw_dir.mkdir()
    (raw_dir / "test").mkdir()
    (raw_dir / "test" / "a.xml").write_text("statement-A", encoding="utf-8")
    (raw_dir / "test" / "b.xml").write_text("statement-B", encoding="utf-8")

    monkeypatch.setattr(ingest, "RAW_ROOT", raw_dir)
    monkeypatch.setattr(
        ingest,
        "NSEFinancialClient",
        _FakeNSEFinancialClient,
    )

    try:
        processed = ingest.process_cached_financial_filings(
            symbol=_SYMBOL,
        )

        assert processed == 2

        with SessionLocal() as db:
            statuses = {
                filing.id: filing.processing_status
                for filing in db.scalars(
                    select(FinancialRawFiling).where(
                        FinancialRawFiling.id.in_(filing_ids)
                    )
                )
            }

            assert statuses[filing_a_id] == "PROCESSED"
            assert statuses[filing_b_id] == "PROCESSED"

            versions = {
                row.raw_filing_id: row
                for row in db.scalars(
                    select(FinancialStatementVersion).where(
                        FinancialStatementVersion.raw_filing_id.in_(
                            filing_ids
                        )
                    )
                )
            }

        assert filing_a_id in versions
        assert filing_b_id in versions

        version_b = versions[filing_b_id]

        reported_b = version_b.reported_values

        # Parser emitted ytd values with no quarterly diff of its own;
        # derivation diffs B against A. If capture were moved after
        # derivation, the reported values would carry derived numbers
        # instead of the raw parser output.
        assert reported_b["_ytd_operating_cash_flow"] == 240_000_000
        assert reported_b["operating_cash_flow"] is None
        assert reported_b["_ytd_revenue"] == 2_400_000_000

        assert version_b.operating_cash_flow == 140_000_000
        assert version_b.capital_expenditure == 20_000_000

        with SessionLocal() as db:
            lineage = db.scalars(
                select(FinancialStatementVersionSource).where(
                    FinancialStatementVersionSource.version_id
                    == version_b.id
                )
            ).all()

        assert lineage
        assert any(
            source.source_raw_filing_id == filing_a_id
            for source in lineage
        )
    finally:
        _cleanup(company_id, filing_ids)
