from types import SimpleNamespace
from app.verification_history import compare_verification_results
from unittest.mock import patch
import pytest
from app.verification_history import compare_verification_runs


def make_result(name, status="PASS", expected=100, actual=100):
    return SimpleNamespace(
        check_name=name,
        status=status,
        expected=expected,
        actual=actual,
    )


def test_detects_status_change():
    older = [make_result("price_count", "PASS")]
    newer = [make_result("price_count", "FAIL")]

    result = compare_verification_results(older, newer)

    assert len(result["changed"]) == 1
    assert result["changed"][0]["differences"] == ["status"]


def test_detects_expected_and_actual_changes():
    older = [make_result("price_count", expected=100, actual=100)]
    newer = [make_result("price_count", expected=200, actual=200)]

    result = compare_verification_results(older, newer)

    assert result["changed"][0]["differences"] == ["expected", "actual"]


def test_detects_added_and_removed_checks():
    older = [
        make_result("price_count"),
        make_result("indicator_count"),
    ]
    newer = [
        make_result("price_count"),
        make_result("benchmark_count"),
    ]

    result = compare_verification_results(older, newer)

    assert [r.check_name for r in result["added"]] == ["benchmark_count"]
    assert [r.check_name for r in result["removed"]] == ["indicator_count"]


def test_detects_unchanged_checks():
    older = [make_result("price_count")]
    newer = [make_result("price_count")]

    result = compare_verification_results(older, newer)

    assert len(result["unchanged"]) == 1
    assert result["changed"] == []


def test_handles_empty_results():
    result = compare_verification_results([], [])

    assert result == {
        "changed": [],
        "added": [],
        "removed": [],
        "unchanged": [],
    }

def test_compare_verification_runs():
    older_run = SimpleNamespace(id=1)
    newer_run = SimpleNamespace(id=2)

    older_results = [make_result("price_count", "PASS")]
    newer_results = [make_result("price_count", "FAIL")]

    with patch(
        "app.verification_history.get_verification_run_details",
        side_effect=[
            (older_run, older_results),
            (newer_run, newer_results),
        ],
    ):
        result = compare_verification_runs(1, 2)

    assert result is not None

    returned_older, returned_newer, comparison = result

    assert returned_older.id == 1
    assert returned_newer.id == 2
    assert comparison["changed"][0]["differences"] == ["status"]


def test_compare_verification_runs_missing_run():
    with patch(
        "app.verification_history.get_verification_run_details",
        side_effect=[
            (None, []),
            (SimpleNamespace(id=2), []),
        ],
    ):
        result = compare_verification_runs(1, 2)

    assert result is None


def test_compare_verification_runs_rejects_same_id():
    with pytest.raises(ValueError, match="must be different"):
        compare_verification_runs(1, 1)