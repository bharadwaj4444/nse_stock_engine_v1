from __future__ import annotations

from datetime import date

import pytest

import app.pipeline as pipeline


def test_daily_passes_selected_trading_date_to_closed_loop(monkeypatch):
    today = date(2026, 10, 22)

    class FakeResult:
        scored = [1, 2, 3]

    calls = []

    monkeypatch.setattr(pipeline, "download_universe", lambda: None)
    monkeypatch.setattr(pipeline, "NSEClient", lambda: object())
    monkeypatch.setattr(pipeline, "calculate_for_date", lambda d: None)

    class FakeCalendar:
        def is_trading_day(self, d):
            return d == today

        def classify(self, d):
            return "trading day"

    monkeypatch.setattr(pipeline, "calendar", FakeCalendar())

    def fake_ingest_bhavcopy(d, client, **kwargs):
        assert d == today
        return 10

    monkeypatch.setattr(pipeline, "ingest_bhavcopy", fake_ingest_bhavcopy)

    class FakeDate(date):
        @classmethod
        def today(cls):
            return today

    monkeypatch.setattr(pipeline, "date", FakeDate)

    def fake_run_closed_loop_for_date(d):
        calls.append(d)
        return FakeResult()

    monkeypatch.setattr(
        pipeline, "run_closed_loop_for_date", fake_run_closed_loop_for_date
    )

    pipeline.daily()

    assert calls == [today]
