
from __future__ import annotations

import argparse
import copy
import json
import sys
from collections import Counter, defaultdict
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.config import settings
from app.db import SessionLocal
from app.ingest import (
    _capture_reported_values,
    derive_quarterly_financials,
)
from app.models import FinancialRawFiling
from app.sources.nse_financials import (
    FinancialFiling,
    NSEFinancialClient,
)


RAW_ROOT = Path(settings.raw_data_dir) / "financial_xbrl"
IST = ZoneInfo("Asia/Kolkata")

VALUE_FIELDS = (
    "revenue",
    "ebitda",
    "ebit",
    "profit_before_tax",
    "net_income",
    "eps",
    "operating_cash_flow",
    "capital_expenditure",
    "free_cash_flow",
    "total_assets",
    "total_equity",
    "total_debt",
    "cash_and_equivalents",
)


def json_value(value):
    if isinstance(value, (date, datetime)):
        return value.isoformat()

    if isinstance(value, Decimal):
        return str(value)

    if isinstance(value, dict):
        return {
            str(key): json_value(item)
            for key, item in value.items()
        }

    if isinstance(value, (list, tuple)):
        return [json_value(item) for item in value]

    return value


def normalize_timestamp(value: datetime | None) -> datetime | None:
    if value is None:
        return None

    if value.tzinfo is None:
        return value.replace(tzinfo=IST)

    return value


def effective_timestamp(filing) -> datetime | None:
    # Revision timestamp takes precedence over broadcast timestamp.
    return normalize_timestamp(
        filing.revised_datetime or filing.broadcast_datetime
    )


def nse_timestamp(value: datetime | None) -> str | None:
    if value is None:
        return None

    return value.strftime("%d-%b-%Y %H:%M:%S")


def load_filings(symbol: str | None):
    with SessionLocal() as session:
        query = session.query(FinancialRawFiling).order_by(
            FinancialRawFiling.id
        )

        rows = query.all()

    if symbol:
        rows = [
            row for row in rows
            if row.symbol.upper() == symbol.upper()
        ]

    return rows


def parse_raw_filing(row, client):
    timestamp = effective_timestamp(row)

    if timestamp is None:
        return None, "MISSING_EFFECTIVE_TIMESTAMP"

    xml_path = RAW_ROOT / Path(row.raw_relative_path)

    if not xml_path.is_file():
        return None, "MISSING_XML"

    try:
        xml_text = xml_path.read_text(encoding="utf-8")

        filing = FinancialFiling(
            symbol=row.symbol,
            company_name="",
            period_end=row.period_end,
            submission_type=row.submission_type or "ORIGINAL",
            audit_status=row.audit_status,
            statement_scope=row.statement_scope or "UNKNOWN",
            details_url=None,
            xbrl_url=row.xbrl_url,
            ixbrl_url=None,
            broadcast_datetime=nse_timestamp(
                row.broadcast_datetime
            ),
            revised_datetime=nse_timestamp(
                row.revised_datetime
            ),
            revision_remarks=row.revision_remarks,
            source_reference=row.source_reference,
            raw={},
        )

        statements = client.parse_xbrl(
            xml_text=xml_text,
            filing=filing,
            effective_filing_date=row.filing_date,
        )

        if not statements:
            return None, "NO_STATEMENTS_RETURNED"

        for statement in statements:
            statement["company_id"] = row.company_id
            statement["_raw_filing_id"] = row.id
            _capture_reported_values(statement)

        return {
            "row": row,
            "effective_at": timestamp,
            "statements": statements,
        }, None

    except Exception as exc:
        return None, f"PARSE_ERROR: {str(exc)[:500]}"


def build_period_index(parsed_filings):
    """
    Index raw filing events by company, scope and reporting period.
    """
    index = defaultdict(list)

    for filing_id, parsed in parsed_filings.items():
        row = parsed["row"]

        key = (
            row.company_id,
            row.statement_scope,
            row.period_end,
        )

        index[key].append(parsed)

    for entries in index.values():
        entries.sort(
            key=lambda item: (
                item["effective_at"],
                item["row"].id,
            )
        )

    return index


def select_as_of_filings(target, period_index):
    """
    Select the latest eligible filing for each reporting period.

    Different-content filings with the same latest effective timestamp
    are ambiguous and are not selected.
    """
    target_row = target["row"]
    target_time = target["effective_at"]

    selected_ids = set()
    ambiguous_periods = []

    company_scope_keys = [
        key for key in period_index
        if (
            key[0] == target_row.company_id
            and key[1] == target_row.statement_scope
        )
    ]

    for key in company_scope_keys:
        entries = period_index[key]

        eligible = [
            item for item in entries
            if item["effective_at"] <= target_time
        ]

        if not eligible:
            continue

        latest_time = max(
            item["effective_at"] for item in eligible
        )

        latest = [
            item for item in eligible
            if item["effective_at"] == latest_time
        ]

        hashes = {
            (item["row"].sha256 or "").lower()
            for item in latest
        }

        if len(hashes) > 1:
            ambiguous_periods.append({
                "period_end": key[2].isoformat(),
                "effective_at": latest_time.isoformat(),
                "filing_ids": [
                    item["row"].id for item in latest
                ],
                "hashes": sorted(hashes),
            })
            continue

        # If the target itself is among identical-content ties,
        # retain the target's identity for this snapshot.
        target_match = next(
            (
                item for item in latest
                if item["row"].id == target_row.id
            ),
            None,
        )

        chosen = target_match or min(
            latest,
            key=lambda item: item["row"].id,
        )

        selected_ids.add(chosen["row"].id)

    return selected_ids, ambiguous_periods


def make_version_result(statement, row, effective_at):
    reported = statement.get("_reported_values") or {}
    lineage = statement.get("_derivation_sources") or []

    derived = {
        field: statement.get(field)
        for field in VALUE_FIELDS
    }

    return {
        "raw_filing_id": row.id,
        "company_id": row.company_id,
        "symbol": row.symbol,
        "period_type": statement.get("period_type"),
        "period_end": statement.get("period_end"),
        "filing_date": statement.get("filing_date"),
        "effective_at": effective_at,
        "statement_scope": row.statement_scope,
        "submission_type": row.submission_type,
        "audit_status": row.audit_status,
        "processing_status": row.processing_status,
        "source_reference": row.source_reference,
        "sha256": row.sha256,
        "reported_values": reported,
        "derived_values": derived,
        "derivation_sources": lineage,
    }


def evaluate_target(target, parsed_filings, period_index):
    target_row = target["row"]

    selected_ids, ambiguous_periods = select_as_of_filings(
        target,
        period_index,
    )

    target_period_is_ambiguous = any(
        item["period_end"] == target_row.period_end.isoformat()
        for item in ambiguous_periods
    )

    target_statements = target["statements"]

    if target_period_is_ambiguous:
        # Preserve the target's reported data, but do not derive
        # against an ambiguous version of its own reporting period.
        results = [
            make_version_result(
                copy.deepcopy(statement),
                target_row,
                target["effective_at"],
            )
            for statement in target_statements
        ]

        return {
            "status": "AMBIGUOUS_TARGET_TIMESTAMP_TIE",
            "versions": results,
            "ambiguous_periods": ambiguous_periods,
        }

    if target_row.id not in selected_ids:
        return {
            "status": "TARGET_NOT_SELECTED",
            "versions": [],
            "ambiguous_periods": ambiguous_periods,
        }

    snapshot = []

    for filing_id in selected_ids:
        parsed = parsed_filings[filing_id]

        for original in parsed["statements"]:
            statement = copy.deepcopy(original)

            # Internal marker allows Original and Revision filings
            # to participate in the same PIT derivation chain.
            statement["submission_type"] = "__PIT_AS_OF__"

            snapshot.append(statement)

    derive_quarterly_financials(snapshot)

    results = []

    for statement in snapshot:
        if statement.get("_raw_filing_id") != target_row.id:
            continue

        results.append(
            make_version_result(
                statement,
                target_row,
                target["effective_at"],
            )
        )

    return {
        "status": "OK",
        "versions": results,
        "ambiguous_periods": ambiguous_periods,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Read-only PIT financial statement version dry run."
    )

    parser.add_argument(
        "--symbol",
        help="Optional symbol filter, e.g. RELIANCE.",
    )

    parser.add_argument(
        "--output",
        default="data/reports/pit_financial_versions_dry_run.json",
        help="Output JSON report path.",
    )

    args = parser.parse_args()

    counts = Counter()
    errors = []
    parsed_filings = {}

    print(f"Raw XML directory: {RAW_ROOT.resolve()}")
    print(f"Symbol filter: {args.symbol or 'ALL'}")
    print("Loading raw filing records...")

    rows = load_filings(args.symbol)
    counts["raw_filings"] = len(rows)

    print(f"Raw filings found: {len(rows)}")
    print("Parsing XML files...")

    client = NSEFinancialClient()

    for index, row in enumerate(rows, start=1):
        parsed, error = parse_raw_filing(row, client)

        if error:
            counts[error.split(":")[0]] += 1
            errors.append({
                "raw_filing_id": row.id,
                "symbol": row.symbol,
                "source_reference": row.source_reference,
                "error": error,
            })
        else:
            parsed_filings[row.id] = parsed
            counts["parsed_raw_filings"] += 1
            counts["parsed_statement_rows"] += len(
                parsed["statements"]
            )

        if index % 500 == 0:
            print(f"Parsed {index}/{len(rows)} raw filings...")

    period_index = build_period_index(parsed_filings)

    print("Evaluating PIT snapshots...")

    versions = []
    ambiguous_events = []

    for index, (filing_id, target) in enumerate(
        parsed_filings.items(),
        start=1,
    ):
        result = evaluate_target(
            target,
            parsed_filings,
            period_index,
        )

        counts[f"target_status_{result['status']}"] += 1

        if result["status"] != "OK":
            ambiguous_events.append({
                "raw_filing_id": filing_id,
                "symbol": target["row"].symbol,
                "status": result["status"],
                "ambiguous_periods": result["ambiguous_periods"],
            })

        for version in result["versions"]:
            versions.append(json_value(version))

            counts["proposed_versions"] += 1

            lineage = version["derivation_sources"]

            if lineage:
                counts["versions_with_lineage"] += 1
                counts["lineage_rows"] += len(lineage)

        if index % 500 == 0:
            print(f"Evaluated {index}/{len(parsed_filings)} targets...")

    report = {
        "report_type": "PIT_FINANCIAL_STATEMENT_VERSION_DRY_RUN",
        "read_only": True,
        "symbol_filter": args.symbol,
        "raw_root": str(RAW_ROOT.resolve()),
        "counts": dict(counts),
        "versions": versions,
        "parse_errors": errors,
        "ambiguous_events": ambiguous_events,
    }

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    output_path.write_text(
        json.dumps(
            report,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    print("\n========== DRY-RUN SUMMARY ==========")

    for key, value in sorted(counts.items()):
        print(f"{key:40} {value:>10}")

    print(f"\nReport: {output_path.resolve()}")
    print("Dry run complete. No database modifications were performed.")


if __name__ == "__main__":
    main()
