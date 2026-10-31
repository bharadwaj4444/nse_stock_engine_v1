
import sys
from datetime import date

import pytest

import app.cli as cli


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
