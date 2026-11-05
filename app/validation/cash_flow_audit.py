
from __future__ import annotations

import csv
import json
import xml.etree.ElementTree as ET

from collections import Counter
from pathlib import Path
from typing import Any


# Exact concepts recognized by the current parser.
OCF_CONCEPTS = {
    "CashFlowsFromUsedInOperatingActivities",
}

CAPEX_CONCEPTS = {
    "PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities",
}

# Cash-flow statement metadata. These are not financial amounts.
METADATA_CONCEPTS = {
    "WhetherCashFlowStatementIsApplicableOnCompany",
    "TypeOfCashFlowStatement",
}

# Broader concept-name patterns for identifying possible cash-flow amounts.
CASH_FLOW_AMOUNT_TERMS = (
    "cashflowsfrom",
    "cashflowfrom",
    "netcashprovidedby",
    "netcashusedin",
    "netcashfrom",
    "cashgeneratedfrom",
    "cashusedin",
    "cashprovidedby",
    "purchaseofpropertyplantandequipment",
    "paymentforpropertyplantandequipment",
    "paymentstoacquirepropertyplantandequipment",
    "capitalexpenditure",
    "proceedsfromsaleofpropertyplantandequipment",
    "acquisitionofpropertyplantandequipment",
)

TARGET_SCOPE_NAMES = {"Consolidated", "Standalone"}


def _local_name(tag: str) -> str:
    """Return XML element name without its namespace."""
    return tag.split("}")[-1]


def _extract_contexts(
    root: ET.Element,
) -> dict[str, dict[str, str | None]]:
    """Extract reporting periods associated with XBRL contexts."""
    contexts = {}

    for element in root.iter():
        if _local_name(element.tag) != "context":
            continue

        context_id = element.attrib.get("id")

        if not context_id:
            continue

        period = next(
            (
                child
                for child in element
                if _local_name(child.tag) == "period"
            ),
            None,
        )

        if period is None:
            continue

        start = next(
            (
                child.text
                for child in period
                if _local_name(child.tag) == "startDate"
            ),
            None,
        )

        end = next(
            (
                child.text
                for child in period
                if _local_name(child.tag) == "endDate"
            ),
            None,
        )

        instant = next(
            (
                child.text
                for child in period
                if _local_name(child.tag) == "instant"
            ),
            None,
        )

        contexts[context_id] = {
            "start": start,
            "end": end,
            "instant": instant,
        }

    return contexts


def _classify_concept(concept_name: str) -> str | None:
    """Classify a concept by its name."""

    if concept_name in METADATA_CONCEPTS:
        return "METADATA"

    if concept_name in OCF_CONCEPTS:
        return "OCF"

    if concept_name in CAPEX_CONCEPTS:
        return "CAPEX"

    normalized = concept_name.lower()

    if any(term in normalized for term in CASH_FLOW_AMOUNT_TERMS):
        return "OTHER_CASH_FLOW"

    return None


def _is_target_period(
    context: dict[str, str | None],
    target_start: str,
    target_end: str,
) -> bool:
    """Check whether a context represents the requested duration."""
    return (
        context.get("start") == target_start
        and context.get("end") == target_end
    )


def audit_xbrl_file(
    path: Path,
    target_start: str,
    target_end: str,
) -> dict[str, Any]:
    """Audit one XBRL filing for cash-flow facts."""

    result = {
        "symbol": "",
        "scope": "",
        "period_end": target_end,
        "file": path.name,
        "file_size": None,
        "status": "AUDIT_ERROR",
        "error": None,
        "ocf_q1": 0,
        "capex_q1": 0,
        "other_cash_flow_q1": 0,
        "metadata_q1": 0,
        "cash_flow_facts_all_periods": 0,
        "cash_flow_facts_target_period": 0,
        "cash_flow_facts_other_periods": 0,
        "metadata_all_periods": 0,
        "cash_flow_concepts_q1": [],
        "metadata_concepts_q1": [],
        "fact_details": [],
    }

    relative = path.parts
    result["symbol"] = relative[-4] if len(relative) >= 4 else ""
    result["scope"] = path.parent.name

    try:
        result["file_size"] = path.stat().st_size

        root = ET.parse(path).getroot()
        contexts = _extract_contexts(root)

        facts = []

        for element in root.iter():
            context_id = element.attrib.get("contextRef")

            if not context_id:
                continue

            concept_name = _local_name(element.tag)
            category = _classify_concept(concept_name)

            if category is None:
                continue

            value = (element.text or "").strip()

            if not value:
                continue

            context = contexts.get(context_id, {})

            facts.append({
                "concept": concept_name,
                "category": category,
                "context_id": context_id,
                "start": context.get("start"),
                "end": context.get("end"),
                "instant": context.get("instant"),
                "value": value,
                "unit": element.attrib.get("unitRef"),
                "decimals": element.attrib.get("decimals"),
            })

        q1_facts = [
            fact
            for fact in facts
            if _is_target_period(
                fact,
                target_start,
                target_end,
            )
        ]

        amount_facts = [
            fact for fact in facts
            if fact["category"] != "METADATA"
        ]

        metadata_facts = [
            fact for fact in facts
            if fact["category"] == "METADATA"
        ]

        q1_amount_facts = [
            fact for fact in q1_facts
            if fact["category"] != "METADATA"
        ]

        q1_metadata = [
            fact for fact in q1_facts
            if fact["category"] == "METADATA"
        ]

        other_period_amount_facts = [
            fact for fact in amount_facts
            if fact not in q1_amount_facts
        ]

        result["ocf_q1"] = sum(
            fact["category"] == "OCF"
            for fact in q1_amount_facts
        )

        result["capex_q1"] = sum(
            fact["category"] == "CAPEX"
            for fact in q1_amount_facts
        )

        result["other_cash_flow_q1"] = sum(
            fact["category"] == "OTHER_CASH_FLOW"
            for fact in q1_amount_facts
        )

        result["metadata_q1"] = len(q1_metadata)

        result["cash_flow_facts_all_periods"] = len(amount_facts)
        result["cash_flow_facts_target_period"] = len(q1_amount_facts)
        result["cash_flow_facts_other_periods"] = len(
            other_period_amount_facts
        )
        result["metadata_all_periods"] = len(metadata_facts)

        result["cash_flow_concepts_q1"] = sorted({
            fact["concept"]
            for fact in q1_amount_facts
        })

        result["metadata_concepts_q1"] = sorted({
            fact["concept"]
            for fact in q1_metadata
        })

        result["fact_details"] = facts

        if q1_amount_facts:
            result["status"] = "QUARTER_CASH_FLOW_FACTS_FOUND"

        elif amount_facts:
            result["status"] = "OTHER_PERIOD_CASH_FLOW_FACTS_ONLY"

        elif metadata_facts:
            result["status"] = "METADATA_ONLY"

        else:
            # This means no facts matched our current concept-name rules.
            # It does not prove that the source contains no cash-flow data.
            result["status"] = "NO_RECOGNIZED_CASH_FLOW_FACTS"

    except Exception as exc:
        result["status"] = "AUDIT_ERROR"
        result["error"] = f"{type(exc).__name__}: {exc}"

    return result

def audit_cash_flow_filings(
    raw_data_dir: str | Path = "data/raw",
    target_start: str = "2025-04-01",
    target_end: str = "2025-06-30",
) -> list[dict[str, Any]]:
    """Audit all XML filings for a reporting period."""

    raw_data_dir = Path(raw_data_dir)

    if not raw_data_dir.exists():
        raise FileNotFoundError(
            f"Raw data directory does not exist: {raw_data_dir}"
        )

    results = []

    for path in sorted(raw_data_dir.rglob("*.xml")):
        if target_end not in path.parts:
            continue

        if path.parent.name not in TARGET_SCOPE_NAMES:
            continue

        results.append(
            audit_xbrl_file(
                path=path,
                target_start=target_start,
                target_end=target_end,
            )
        )

    return results


def summarize_cash_flow_audit(
    results: list[dict[str, Any]],
) -> dict[str, Any]:
    """Summarize audit classifications and cash-flow findings."""

    status_counts = Counter(
        row["status"]
        for row in results
    )

    return {
        "total_files": len(results),
        "successful_files": sum(
            1 for row in results if not row["error"]
        ),
        "error_files": sum(
            1 for row in results if row["error"]
        ),
        "no_recognized_cash_flow_facts": status_counts[
            "NO_RECOGNIZED_CASH_FLOW_FACTS"
        ],
        "metadata_only": status_counts["METADATA_ONLY"],
        "other_period_cash_flow_facts_only": status_counts[
            "OTHER_PERIOD_CASH_FLOW_FACTS_ONLY"
        ],
        "quarter_cash_flow_facts_found": status_counts[
            "QUARTER_CASH_FLOW_FACTS_FOUND"
        ],
        "files_with_q1_ocf": sum(
            1 for row in results if row["ocf_q1"]
        ),
        "files_with_q1_capex": sum(
            1 for row in results if row["capex_q1"]
        ),
        "files_with_q1_other_cash_flow": sum(
            1 for row in results if row["other_cash_flow_q1"]
        ),
    }

def export_cash_flow_audit_csv(
    results: list[dict[str, Any]],
    output_path: str | Path,
) -> None:
    """Export detailed audit results to CSV."""

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    columns = [
        "symbol",
        "scope",
        "period_end",
        "file",
        "file_size",
        "status",
        "error",
        "ocf_q1",
        "capex_q1",
        "other_cash_flow_q1",
        "metadata_q1",
        "cash_flow_facts_all_periods",
        "cash_flow_facts_target_period",
        "cash_flow_facts_other_periods",
        "metadata_all_periods",
        "cash_flow_concepts_q1",
        "metadata_concepts_q1",
        "fact_details",
    ]

    with output_path.open(
        "w",
        newline="",
        encoding="utf-8-sig",
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=columns,
        )

        writer.writeheader()

        for row in results:
            output_row = row.copy()

            for field in (
                "cash_flow_concepts_q1",
                "metadata_concepts_q1",
                "fact_details",
            ):
                output_row[field] = json.dumps(
                    row[field],
                    ensure_ascii=False,
                )

            writer.writerow(output_row)
