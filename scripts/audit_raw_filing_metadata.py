from __future__ import annotations

import json
import os
from collections import Counter
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from app.config import settings
from app.db import SessionLocal
from app.models import FinancialRawFiling

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))


RAW_ROOT = Path(settings.raw_data_dir) / "financial_xbrl"
IST = ZoneInfo("Asia/Kolkata")

counts = Counter()
examples: dict[str, list[str]] = {}


def report_issue(kind: str, filing, detail: str) -> None:
    counts[kind] += 1
    examples.setdefault(kind, [])

    if len(examples[kind]) < 5:
        examples[kind].append(
            f"id={filing.id}, symbol={filing.symbol}, "
            f"reference={filing.source_reference}: {detail}"
        )


def normalize(value) -> str:
    return str(value or "").strip()


def parse_nse_datetime(value: str) -> datetime:
    """
    Parse NSE filing timestamps and interpret naive values as IST.
    """
    value = value.strip()

    try:
        parsed = datetime.strptime(value, "%d-%b-%Y %H:%M:%S")
    except ValueError:
        parsed = datetime.fromisoformat(value)

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=IST)

    return parsed


def normalized_path(path: Path) -> str:
    return os.path.normcase(str(path.resolve()))


def audit_filing(filing) -> None:
    counts["records_checked"] += 1

    xml_path = RAW_ROOT / Path(filing.raw_relative_path)
    metadata_path = xml_path.with_suffix(".json")

    if not xml_path.is_file():
        report_issue("missing_xml", filing, str(xml_path))
        return

    if not metadata_path.is_file():
        report_issue("missing_json", filing, str(metadata_path))
        return

    try:
        data = json.loads(metadata_path.read_text(encoding="utf-8"))
    except Exception as exc:
        report_issue("invalid_json", filing, str(exc))
        return

    # Verify metadata identity.
    if normalize(data.get("symbol")).upper() != filing.symbol.upper():
        report_issue("symbol_mismatch", filing, data.get("symbol"))

    try:
        metadata_period = date.fromisoformat(data["period_end"])
        if metadata_period != filing.period_end:
            report_issue("period_mismatch", filing, str(metadata_period))
    except Exception as exc:
        report_issue("invalid_period", filing, str(exc))

    if normalize(data.get("statement_scope")).lower() != (
        filing.statement_scope or ""
    ).strip().lower():
        report_issue(
            "scope_mismatch",
            filing,
            data.get("statement_scope"),
        )

    if normalize(data.get("source_reference")) != normalize(
        filing.source_reference
    ):
        report_issue(
            "reference_mismatch",
            filing,
            data.get("source_reference"),
        )

    if normalize(data.get("sha256")).lower() != normalize(
        filing.sha256
    ).lower():
        report_issue("sha256_mismatch", filing, data.get("sha256"))

    try:
        metadata_size = int(data["file_size"])
        if metadata_size != filing.file_size:
            report_issue(
                "file_size_mismatch",
                filing,
                f"JSON={metadata_size}, DB={filing.file_size}",
            )
    except Exception as exc:
        report_issue("invalid_file_size", filing, str(exc))

    # Verify that the JSON points to the same XML file as the DB row.
    raw_xml_path = data.get("raw_xml_path")

    if not raw_xml_path:
        report_issue("missing_json_xml_path", filing, "raw_xml_path absent")
    else:
        json_xml_path = Path(raw_xml_path)

        if not json_xml_path.is_absolute():
            json_xml_path = Path.cwd() / json_xml_path

        if normalized_path(json_xml_path) != normalized_path(xml_path):
            report_issue(
                "xml_path_mismatch",
                filing,
                f"JSON={json_xml_path}, DB={xml_path}",
            )

    # Validate timestamp formats without modifying anything.
    for field in ("broadcast_datetime", "revised_datetime"):
        value = data.get(field)

        if value:
            try:
                parse_nse_datetime(value)
                counts[f"valid_{field}"] += 1
            except Exception as exc:
                report_issue(
                    f"invalid_{field}",
                    filing,
                    f"{value!r}: {exc}",
                )

    if not data.get("broadcast_datetime") and not data.get(
        "revised_datetime"
    ):
        counts["no_filing_timestamp"] += 1

    if data.get("revision_remarks"):
        counts["records_with_revision_remarks"] += 1


def main() -> None:
    print(f"Raw filing directory: {RAW_ROOT.resolve()}")

    with SessionLocal() as session:
        filings = session.query(FinancialRawFiling).order_by(
            FinancialRawFiling.id
        ).all()

        counts["database_records"] = len(filings)

        for filing in filings:
            audit_filing(filing)

    print("\n========== AUDIT SUMMARY ==========")

    for key, value in sorted(counts.items()):
        print(f"{key:35} {value:>10}")

    print("\n========== ISSUE EXAMPLES ==========")

    if not examples:
        print("No identity, path, JSON or timestamp parsing issues found.")
    else:
        for kind, rows in sorted(examples.items()):
            print(f"\n{kind}:")
            for row in rows:
                print(f"  {row}")

    print("\nAudit complete. No database modifications were performed.")


if __name__ == "__main__":
    main()