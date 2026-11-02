from __future__ import annotations

from datetime import date
from types import SimpleNamespace

from fastapi.testclient import TestClient

import app.api as api
from app.api import app


client = TestClient(app)


class FakeRankingStore:
    def get_rankings(self, trade_date, statement_scope):
        return [
            SimpleNamespace(
                company_id=1,
                trade_date=trade_date,
                statement_scope=statement_scope,
                score=75.0,
                red_green="green",
                momentum_score=60.0,
                profitability_score=80.0,
                leverage_score=40.0,
                valuation_score=50.0,
                overall_rank=1,
                overall_percentile=0.9,
                valid_feature_count=4,
                valid_category_count=4,
            ),
        ]


class FakeHoldStore:
    def get_hold_decisions(self, trade_date):
        return [
            SimpleNamespace(
                company_id=1,
                trade_date=trade_date,
                action="hold",
                score=75.0,
                red_green="green",
                action_reason="initial_hold",
                hold_until=date(2026, 10, 24),
                sell_target_price=None,
                sell_target_date=None,
                expected_return=None,
            ),
        ]


def test_red_green_recommendations_endpoint(monkeypatch):
    monkeypatch.setattr(
        api,
        "RecommendationPersistenceAdapter",
        lambda session: FakeRankingStore(),
    )

    response = client.get(
        "/recommendations/red-green",
        params={"trade_date": "2026-10-22"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["trade_date"] == "2026-10-22"
    assert body["red_green_threshold"] == 50.0
    assert len(body["recommendations"]) == 1
    assert body["recommendations"][0]["score"] == 75.0
    assert body["recommendations"][0]["red_green"] == "green"


def test_hold_decisions_endpoint(monkeypatch):
    monkeypatch.setattr(
        api,
        "RecommendationPersistenceAdapter",
        lambda session: FakeHoldStore(),
    )

    response = client.get(
        "/recommendations/holds",
        params={"trade_date": "2026-10-22"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["trade_date"] == "2026-10-22"
    assert len(body["holds"]) == 1
    assert body["holds"][0]["action"] == "hold"
    assert body["holds"][0]["red_green"] == "green"
