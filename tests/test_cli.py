
import sys
from datetime import date

import pytest

import app.cli as cli
from datetime import date, datetime, timezone
from types import SimpleNamespace


class FakeResult:
    def scalar_one(self):
        return 1

    def scalars(self):
        return self

    def all(self):
        return [101]


class FakeConnection:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def execute(self, statement, params=None):
        return FakeResult()


class FakeEngine:
    def connect(self):
        return FakeConnection()


def test_analyze_exits_when_post_analysis_verification_fails(monkeypatch):
    target_date = date(2026, 10, 22)

    monkeypatch.setattr(sys, "argv", [
        "nse-engine",
        "analyze",
        "--date",
        target_date.isoformat(),
    ])

    monkeypatch.setattr(cli, "engine", FakeEngine())

    monkeypatch.setattr(
        cli,
        "build_market_metrics_for_company",
        lambda *args: 1,
    )
    monkeypatch.setattr(
        cli,
        "build_ratios_for_all",
        lambda: 1,
    )
    monkeypatch.setattr(
        cli,
        "build_valuations_for_all_companies",
        lambda *args: (1, 1),
    )
    monkeypatch.setattr(
        cli,
        "build_historical_features",
        lambda *args: 1,
    )
    monkeypatch.setattr(
        cli,
        "build_feature_scores",
        lambda *args: 1,
    )
    monkeypatch.setattr(
        cli,
        "build_stock_rankings",
        lambda *args: 1,
    )

    verification_dates = []

    def failed_verification(check_date, trigger="verify"):
        verification_dates.append(check_date)
        verification_dates.append(trigger)
        return False

    monkeypatch.setattr(cli, "print_report", failed_verification)

    with pytest.raises(SystemExit) as exc_info:
        cli.main()

    assert exc_info.value.code == 1
    assert verification_dates == [target_date, "analyze"]

def test_verification_history_displays_runs(monkeypatch, capsys):
    monkeypatch.setattr(
        sys,
        "argv",
        ["nse-engine", "verification-history"],
    )

    runs = [
        SimpleNamespace(
            id=9,
            trade_date=date(2026, 10, 22),
            trigger="verify",
            completed_at=datetime(
                2026, 10, 31, 15, 41, 55,
                tzinfo=timezone.utc,
            ),
            check_count=13,
            failure_count=0,
            warning_count=2,
        )
    ]

    captured = {}

    def fake_history(target_date=None, limit=20):
        captured["date"] = target_date
        captured["limit"] = limit
        return runs

    monkeypatch.setattr(cli, "get_verification_history", fake_history)

    cli.main()

    output = capsys.readouterr().out

    assert captured == {"date": None, "limit": 20}
    assert "Verification History" in output
    assert "2026-10-22" in output
    assert "verify" in output
    assert "13" in output
    assert "Total runs displayed: 1" in output


def test_verification_history_filters_by_date(monkeypatch):
    target_date = date(2026, 10, 22)

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "nse-engine",
            "verification-history",
            "--date",
            target_date.isoformat(),
        ],
    )

    captured = {}

    def fake_history(target_date=None, limit=20):
        captured["date"] = target_date
        captured["limit"] = limit
        return []

    monkeypatch.setattr(cli, "get_verification_history", fake_history)

    cli.main()

    assert captured == {"date": target_date, "limit": 20}


def test_verification_history_applies_limit(monkeypatch):
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "nse-engine",
            "verification-history",
            "--limit",
            "5",
        ],
    )

    captured = {}

    def fake_history(target_date=None, limit=20):
        captured["date"] = target_date
        captured["limit"] = limit
        return []

    monkeypatch.setattr(cli, "get_verification_history", fake_history)

    cli.main()

    assert captured == {"date": None, "limit": 5}

def test_verification_details_displays_run_and_results(monkeypatch, capsys):
    monkeypatch.setattr(
        sys,
        "argv",
        ["nse-engine", "verification-details", "--run-id", "9"],
    )

    run = SimpleNamespace(
        id=9,
        trade_date=date(2026, 10, 22),
        trigger="verify",
        started_at=datetime(2026, 10, 31, 15, 41, 54, tzinfo=timezone.utc),
        completed_at=datetime(2026, 10, 31, 15, 41, 55, tzinfo=timezone.utc),
        check_count=13,
        failure_count=0,
        warning_count=2,
    )

    results = [
        SimpleNamespace(
            status="PASS",
            check_name="Daily price input",
            expected=None,
            actual=2591,
            details="2591 active companies priced",
        ),
        SimpleNamespace(
            status="WARN",
            check_name="Active-universe price coverage",
            expected=2613,
            actual=2591,
            details="22 active companies have no price row",
        ),
    ]

    captured = {}

    def fake_details(run_id):
        captured["run_id"] = run_id
        return run, results

    monkeypatch.setattr(cli, "get_verification_run_details", fake_details)

    cli.main()

    output = capsys.readouterr().out

    assert captured["run_id"] == 9
    assert "Verification Run Details" in output
    assert "Trade Date   : 2026-10-22" in output
    assert "Trigger      : verify" in output
    assert "Total Checks : 13" in output
    assert "Failures     : 0" in output
    assert "Warnings     : 2" in output
    assert "Daily price input" in output
    assert "Active-universe price coverage" in output
    assert "2591" in output
    assert "22 active companies have no price row" in output


def test_verification_details_handles_unknown_run(monkeypatch, capsys):
    monkeypatch.setattr(
        sys,
        "argv",
        ["nse-engine", "verification-details", "--run-id", "999999"],
    )

    monkeypatch.setattr(
        cli,
        "get_verification_run_details",
        lambda run_id: (None, []),
    )

    cli.main()

    output = capsys.readouterr().out

    assert "Verification run 999999 not found." in output


def test_verification_details_requires_run_id(monkeypatch):
    monkeypatch.setattr(
        sys,
        "argv",
        ["nse-engine", "verification-details"],
    )

    with pytest.raises(SystemExit) as exc_info:
        cli.main()

    assert exc_info.value.code == 2



def test_verification_compare_displays_results(monkeypatch, capsys):
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "nse-engine",
            "verification-compare",
            "--older-run-id",
            "9",
            "--newer-run-id",
            "30",
        ],
    )

    older_run = SimpleNamespace(
        id=9,
        trade_date=date(2026, 10, 22),
        trigger="verify",
    )
    newer_run = SimpleNamespace(
        id=30,
        trade_date=date(2026, 10, 22),
        trigger="verify",
    )

    changed = {
        "check_name": "Daily price input",
        "differences": ["status", "actual"],
        "older": SimpleNamespace(
            status="PASS", expected=None, actual=2591
        ),
        "newer": SimpleNamespace(
            status="FAIL", expected=None, actual=2500
        ),
    }

    comparison = {
        "changed": [changed],
        "added": [SimpleNamespace(check_name="New check", status="PASS")],
        "removed": [SimpleNamespace(check_name="Old check", status="WARN")],
        "unchanged": [SimpleNamespace(check_name="Existing check", status="PASS")],
    }

    captured = {}

    def fake_compare(older_run_id, newer_run_id):
        captured["ids"] = (older_run_id, newer_run_id)
        return older_run, newer_run, comparison

    monkeypatch.setattr(cli, "compare_verification_runs", fake_compare)

    cli.main()

    output = capsys.readouterr().out

    assert captured["ids"] == (9, 30)
    assert "Verification Run Comparison" in output
    assert "Changed checks  : 1" in output
    assert "Added checks    : 1" in output
    assert "Removed checks  : 1" in output
    assert "Unchanged checks: 1" in output
    assert "Daily price input" in output
    assert "New check" in output
    assert "Old check" in output
    assert "Existing check" in output


def test_verification_compare_handles_unknown_run(monkeypatch, capsys):
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "nse-engine",
            "verification-compare",
            "--older-run-id",
            "9",
            "--newer-run-id",
            "999999",
        ],
    )

    monkeypatch.setattr(
        cli,
        "compare_verification_runs",
        lambda older_run_id, newer_run_id: None,
    )

    cli.main()

    output = capsys.readouterr().out

    assert "One or both verification runs were not found." in output


def test_verification_compare_requires_both_run_ids(monkeypatch):
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "nse-engine",
            "verification-compare",
            "--older-run-id",
            "9",
        ],
    )

    with pytest.raises(SystemExit) as exc_info:
        cli.main()

    assert exc_info.value.code == 2