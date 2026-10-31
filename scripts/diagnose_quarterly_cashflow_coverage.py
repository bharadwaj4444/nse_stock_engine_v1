
from __future__ import annotations

import hashlib
import csv
import xml.etree.ElementTree as ET

from collections import Counter, defaultdict
from pathlib import Path

from sqlalchemy import text

from app.db import engine


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_ROOT = (PROJECT_ROOT / "data" / "raw" / "financial_xbrl").resolve()
OUTPUT_DIR = PROJECT_ROOT / "reports" / "cashflow_diagnostic"

DETAIL_FILE = OUTPUT_DIR / "quarterly_cashflow_xml_detail.csv"
SUMMARY_FILE = OUTPUT_DIR / "quarterly_cashflow_xml_summary.csv"

# Known NSE/XBRL concepts observed in the filings.
OCF_CONCEPTS = {
    "cashflowsfromusedinoperatingactivities",
    "cashflowsfromusedinoperations",
}

CAPEX_CONCEPTS = {
    "purchaseofpropertyplantandequipmentclassifiedasinvestingactivities",
}


QUERY = """
SELECT
    r.id AS raw_filing_id,
    r.company_id,
    r.symbol,
    r.period_end,
    r.filing_date,
    r.statement_scope,
    r.submission_type,
    r.source_reference,
    r.raw_relative_path,
    r.file_size,
    r.sha256,
    r.processing_status,
    r.processing_error
FROM financial_raw_filings r
ORDER BY
    r.period_end,
    r.statement_scope,
    r.symbol,
    r.id
"""


def local_name(tag: str) -> str:
    """Remove the XML namespace from an element name."""
    return tag.split("}")[-1].lower()


def inspect_xml(path: Path) -> dict:
    """Inspect XML element names without changing the source file."""

    names = set()

    try:
        for _, element in ET.iterparse(path, events=("start",)):
            names.add(local_name(element.tag))

        ocf_found = bool(names & OCF_CONCEPTS)
        capex_found = bool(names & CAPEX_CONCEPTS)

        cash_names = sorted(
            name for name in names
            if "cash" in name
        )

        return {
            "xml_status": "OK",
            "ocf_concept_found": ocf_found,
            "capex_concept_found": capex_found,
            "both_concepts_found": ocf_found and capex_found,
            "cash_related_concept_count": len(cash_names),
            "cash_related_concepts": ";".join(cash_names),
            "ocf_concepts": ";".join(sorted(names & OCF_CONCEPTS)),
            "capex_concepts": ";".join(sorted(names & CAPEX_CONCEPTS)),
            "error": "",
        }

    except ET.ParseError as exc:
        status = "INVALID_XML"
        error = str(exc)

    except OSError as exc:
        status = "READ_ERROR"
        error = str(exc)

    return {
        "xml_status": status,
        "ocf_concept_found": False,
        "capex_concept_found": False,
        "both_concepts_found": False,
        "cash_related_concept_count": 0,
        "cash_related_concepts": "",
        "ocf_concepts": "",
        "capex_concepts": "",
        "error": error,
    }


def classify(result: dict) -> str:
    if result["xml_status"] != "OK":
        return result["xml_status"]

    if result["both_concepts_found"]:
        return "BOTH_FOUND"

    if result["ocf_concept_found"]:
        return "OCF_ONLY"

    if result["capex_concept_found"]:
        return "CAPEX_ONLY"

    if result["cash_related_concept_count"] > 0:
        return "OTHER_CASH_CONCEPTS"

    return "NO_CASH_CONCEPTS"

def verify_file_integrity(path: Path, expected_size: int, expected_sha256: str) -> dict:
    if not path.is_file():
        return {
            "file_exists": False,
            "actual_file_size": None,
            "actual_sha256": "",
            "size_matches": False,
            "sha256_matches": False,
        }

    digest = hashlib.sha256()
    actual_size = 0

    with path.open("rb") as file:
        while chunk := file.read(1024 * 1024):
            actual_size += len(chunk)
            digest.update(chunk)

    actual_hash = digest.hexdigest()

    return {
        "file_exists": True,
        "actual_file_size": actual_size,
        "actual_sha256": actual_hash,
        "size_matches": actual_size == expected_size,
        "sha256_matches": actual_hash.lower() == (expected_sha256 or "").lower(),
    }

def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    with engine.connect() as connection:
        filings = connection.execute(
            text(QUERY)
        ).mappings().all()

    print(f"Quarterly filing records: {len(filings)}")

    # Parse each unique XML path only once.
    cache = {}
    detail_rows = []

    for index, filing in enumerate(filings, start=1):
        relative_path = Path(filing["raw_relative_path"])

        # Prevent paths outside the configured raw-data directory.
        xml_path = (RAW_ROOT / relative_path).resolve()

        if not xml_path.is_relative_to(RAW_ROOT):
            result = {
                "xml_status": "INVALID_PATH",
                "ocf_concept_found": False,
                "capex_concept_found": False,
                "both_concepts_found": False,
                "cash_related_concept_count": 0,
                "cash_related_concepts": "",
                "ocf_concepts": "",
                "capex_concepts": "",
                "error": "Path resolves outside RAW_ROOT",
            }
        elif not xml_path.is_file():
            result = {
                "xml_status": "MISSING_FILE",
                "ocf_concept_found": False,
                "capex_concept_found": False,
                "both_concepts_found": False,
                "cash_related_concept_count": 0,
                "cash_related_concepts": "",
                "ocf_concepts": "",
                "capex_concepts": "",
                "error": "File does not exist",
            }
        else:
            integrity = verify_file_integrity(
                xml_path,
                filing["file_size"],
                filing["sha256"],
            ) if xml_path.is_file() else {
                "file_exists": False,
                "actual_file_size": None,
                "actual_sha256": "",
                "size_matches": False,
                "sha256_matches": False,
            }
            key = str(xml_path).lower()

            if key not in cache:
                cache[key] = inspect_xml(xml_path)

            result = cache[key]

        period_end = filing["period_end"]

        row = {
            "raw_filing_id": filing["raw_filing_id"],
            "company_id": filing["company_id"],
            "symbol": filing["symbol"],
            "period_end": period_end.isoformat(),
            "filing_date":filing["filing_date"],
            "financial_year": period_end.year,
            "period_month": period_end.month,
            "statement_scope": filing["statement_scope"],
            "submission_type": filing["submission_type"],
            "source_reference": filing["source_reference"],
            "raw_relative_path": filing["raw_relative_path"],
            "processing_status": filing["processing_status"],
            "processing_error":filing["processing_error"],
            "classification": classify(result),
            **result,
            **integrity,
        }

        detail_rows.append(row)

        if index % 1000 == 0:
            print(f"Scanned filing records: {index}/{len(filings)}")

    # Detail CSV.
    if detail_rows:
        with DETAIL_FILE.open(
            "w", newline="", encoding="utf-8-sig"
        ) as file:
            writer = csv.DictWriter(
                file,
                fieldnames=list(detail_rows[0].keys()),
            )
            writer.writeheader()
            writer.writerows(detail_rows)

    # Aggregate by year, period and scope.
    grouped = defaultdict(list)

    for row in detail_rows:
        key = (
            row["financial_year"],
            row["period_month"],
            row["statement_scope"],
        )
        grouped[key].append(row)

    summary_rows = []

    for (year, month, scope), rows in sorted(grouped.items()):
        counts = Counter(
            row["classification"] for row in rows
        )

        summary_rows.append({
            "financial_year": year,
            "period_month": month,
            "statement_scope": scope,
            "filing_records": len(rows),
            "unique_xml_paths": len({
                row["raw_relative_path"] for row in rows
            }),
            "ocf_found": counts["BOTH_FOUND"] + counts["OCF_ONLY"],
            "capex_found": counts["BOTH_FOUND"] + counts["CAPEX_ONLY"],
            "both_found": counts["BOTH_FOUND"],
            "ocf_only": counts["OCF_ONLY"],
            "capex_only": counts["CAPEX_ONLY"],
            "other_cash_concepts": counts["OTHER_CASH_CONCEPTS"],
            "no_cash_concepts": counts["NO_CASH_CONCEPTS"],
            "missing_files": counts["MISSING_FILE"],
            "invalid_xml": counts["INVALID_XML"],
            "read_errors": counts["READ_ERROR"],
            "invalid_paths": counts["INVALID_PATH"],
        })

    if summary_rows:
        with SUMMARY_FILE.open(
            "w", newline="", encoding="utf-8-sig"
        ) as file:
            writer = csv.DictWriter(
                file,
                fieldnames=list(summary_rows[0].keys()),
            )
            writer.writeheader()
            writer.writerows(summary_rows)

    total = Counter(
        row["classification"] for row in detail_rows
    )

    print("\n========== CASH FLOW XML DIAGNOSTIC ==========")
    print(f"Filing records:         {len(detail_rows)}")
    print(f"Unique XML paths:       {len(set(r['raw_relative_path'] for r in detail_rows))}")
    print(f"Both OCF and capex:     {total['BOTH_FOUND']}")
    print(f"OCF only:               {total['OCF_ONLY']}")
    print(f"Capex only:             {total['CAPEX_ONLY']}")
    print(f"Other cash concepts:    {total['OTHER_CASH_CONCEPTS']}")
    print(f"No cash concepts:       {total['NO_CASH_CONCEPTS']}")
    print(f"Missing files:          {total['MISSING_FILE']}")
    print(f"Invalid XML:            {total['INVALID_XML']}")
    print(f"Read errors:            {total['READ_ERROR']}")
    print(f"Invalid paths:          {total['INVALID_PATH']}")

    print("\nOutput files:")
    print(DETAIL_FILE)
    print(SUMMARY_FILE)


if __name__ == "__main__":
    main()
