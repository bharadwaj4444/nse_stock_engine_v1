
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