
from pathlib import Path

import pytest

from app.validation.cash_flow_audit import (
    audit_xbrl_file,
    summarize_cash_flow_audit,
)


TARGET_START = "2025-04-01"
TARGET_END = "2025-06-30"

XBRLI_NAMESPACE = "http://www.xbrl.org/2003/instance"


def write_xbrl(
    path: Path,
    contexts: dict[str, tuple[str, str]],
    facts: list[tuple[str, str, str]],
) -> Path:
    """Create a small synthetic XBRL document.

    facts: (concept_name, context_id, value)
    """

    context_xml = ""

    for context_id, (start, end) in contexts.items():
        context_xml += f"""
        <xbrli:context id="{context_id}">
            <xbrli:entity>
                <xbrli:identifier scheme="test">TEST</xbrli:identifier>
            </xbrli:entity>
            <xbrli:period>
                <xbrli:startDate>{start}</xbrli:startDate>
                <xbrli:endDate>{end}</xbrli:endDate>
            </xbrli:period>
        </xbrli:context>
        """

    fact_xml = ""

    for concept, context_id, value in facts:
        fact_xml += f"""
        <ex:{concept}
            contextRef="{context_id}"
            unitRef="INR"
            decimals="0">{value}</ex:{concept}>
        """

    xml = f"""
    <xbrli:xbrl
        xmlns:xbrli="{XBRLI_NAMESPACE}"
        xmlns:ex="http://example.com/test">

        {context_xml}
        {fact_xml}

    </xbrli:xbrl>
    """

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(xml, encoding="utf-8")

    return path


def test_exact_quarter_ocf_and_capex_are_detected(tmp_path):
    path = write_xbrl(
        tmp_path / "TEST" / "2025-06-30" / "Consolidated" / "filing.xml",
        {
            "Q1": (TARGET_START, TARGET_END),
        },
        [
            (
                "CashFlowsFromUsedInOperatingActivities",
                "Q1",
                "100000",
            ),
            (
                "PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities",
                "Q1",
                "25000",
            ),
        ],
    )

    result = audit_xbrl_file(path, TARGET_START, TARGET_END)

    assert result["status"] == "QUARTER_CASH_FLOW_FACTS_FOUND"
    assert result["ocf_q1"] == 1
    assert result["capex_q1"] == 1
    assert result["cash_flow_facts_target_period"] == 2
    assert result["cash_flow_facts_other_periods"] == 0


def test_six_month_cumulative_facts_are_not_classified_as_quarter(
    tmp_path,
):
    path = write_xbrl(
        tmp_path / "TEST" / "2025-06-30" / "Consolidated" / "filing.xml",
        {
            "YTD": ("2025-01-01", TARGET_END),
        },
        [
            (
                "CashFlowsFromUsedInOperatingActivities",
                "YTD",
                "175000",
            ),
            (
                "PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities",
                "YTD",
                "30000",
            ),
        ],
    )

    result = audit_xbrl_file(path, TARGET_START, TARGET_END)

    assert result["status"] == "OTHER_PERIOD_CASH_FLOW_FACTS_ONLY"
    assert result["ocf_q1"] == 0
    assert result["capex_q1"] == 0
    assert result["cash_flow_facts_all_periods"] == 2
    assert result["cash_flow_facts_target_period"] == 0
    assert result["cash_flow_facts_other_periods"] == 2


def test_partial_quarter_disclosure_is_detected(tmp_path):
    path = write_xbrl(
        tmp_path / "TEST" / "2025-06-30" / "Standalone" / "filing.xml",
        {
            "Q1": (TARGET_START, TARGET_END),
        },
        [
            (
                "CashFlowsFromUsedInOperatingActivities",
                "Q1",
                "100000",
            ),
        ],
    )

    result = audit_xbrl_file(path, TARGET_START, TARGET_END)

    assert result["status"] == "QUARTER_CASH_FLOW_FACTS_FOUND"
    assert result["ocf_q1"] == 1
    assert result["capex_q1"] == 0


def test_target_quarter_and_other_period_facts_can_coexist(tmp_path):
    path = write_xbrl(
        tmp_path / "TEST" / "2025-06-30" / "Consolidated" / "filing.xml",
        {
            "Q1": (TARGET_START, TARGET_END),
            "YTD": ("2025-01-01", TARGET_END),
        },
        [
            (
                "CashFlowsFromUsedInOperatingActivities",
                "Q1",
                "100000",
            ),
            (
                "PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities",
                "YTD",
                "30000",
            ),
        ],
    )

    result = audit_xbrl_file(path, TARGET_START, TARGET_END)

    assert result["status"] == "QUARTER_CASH_FLOW_FACTS_FOUND"
    assert result["cash_flow_facts_target_period"] == 1
    assert result["cash_flow_facts_other_periods"] == 1
    assert result["ocf_q1"] == 1
    assert result["capex_q1"] == 0


def test_metadata_only_filing(tmp_path):
    path = write_xbrl(
        tmp_path / "TEST" / "2025-06-30" / "Standalone" / "filing.xml",
        {
            "Q1": (TARGET_START, TARGET_END),
        },
        [
            (
                "WhetherCashFlowStatementIsApplicableOnCompany",
                "Q1",
                "Yes",
            ),
        ],
    )

    result = audit_xbrl_file(path, TARGET_START, TARGET_END)

    assert result["status"] == "METADATA_ONLY"
    assert result["metadata_all_periods"] == 1
    assert result["cash_flow_facts_all_periods"] == 0


def test_unrecognized_facts_are_not_misclassified(tmp_path):
    path = write_xbrl(
        tmp_path / "TEST" / "2025-06-30" / "Standalone" / "filing.xml",
        {
            "Q1": (TARGET_START, TARGET_END),
        },
        [
            ("RevenueFromOperations", "Q1", "500000"),
        ],
    )

    result = audit_xbrl_file(path, TARGET_START, TARGET_END)

    assert result["status"] == "NO_RECOGNIZED_CASH_FLOW_FACTS"
    assert result["cash_flow_facts_all_periods"] == 0


def test_malformed_xml_returns_audit_error(tmp_path):
    path = (
        tmp_path
        / "TEST"
        / "2025-06-30"
        / "Standalone"
        / "malformed.xml"
    )

    path.parent.mkdir(parents=True)
    path.write_text("<xbrli:xbrl><broken>", encoding="utf-8")

    result = audit_xbrl_file(path, TARGET_START, TARGET_END)

    assert result["status"] == "AUDIT_ERROR"
    assert result["error"] is not None


def test_missing_file_returns_audit_error(tmp_path):
    path = (
        tmp_path
        / "TEST"
        / "2025-06-30"
        / "Standalone"
        / "missing.xml"
    )

    result = audit_xbrl_file(path, TARGET_START, TARGET_END)

    assert result["status"] == "AUDIT_ERROR"
    assert result["error"] is not None


def test_summary_counts_all_classifications(tmp_path):
    path1 = write_xbrl(
        tmp_path / "TEST1" / "2025-06-30" / "Standalone" / "one.xml",
        {"Q1": (TARGET_START, TARGET_END)},
        [
            (
                "CashFlowsFromUsedInOperatingActivities",
                "Q1",
                "100",
            ),
        ],
    )

    path2 = write_xbrl(
        tmp_path / "TEST2" / "2025-06-30" / "Standalone" / "two.xml",
        {"YTD": ("2025-01-01", TARGET_END)},
        [
            (
                "CashFlowsFromUsedInOperatingActivities",
                "YTD",
                "200",
            ),
        ],
    )

    path3 = write_xbrl(
        tmp_path / "TEST3" / "2025-06-30" / "Standalone" / "three.xml",
        {"Q1": (TARGET_START, TARGET_END)},
        [
            (
                "WhetherCashFlowStatementIsApplicableOnCompany",
                "Q1",
                "Yes",
            ),
        ],
    )

    results = [
        audit_xbrl_file(path1, TARGET_START, TARGET_END),
        audit_xbrl_file(path2, TARGET_START, TARGET_END),
        audit_xbrl_file(path3, TARGET_START, TARGET_END),
    ]

    summary = summarize_cash_flow_audit(results)

    assert summary["total_files"] == 3
    assert summary["successful_files"] == 3
    assert summary["error_files"] == 0
    assert summary["quarter_cash_flow_facts_found"] == 1
    assert summary["other_period_cash_flow_facts_only"] == 1
    assert summary["metadata_only"] == 1
