from __future__ import annotations

from datetime import date

import pytest

from app.core.engine import run_closed_loop
from app.core.news_override import apply_override, assess_significance, build_override
from app.core.holds import DEFAULT_HOLD_DURATION_DAYS, decide_hold
from app.core.refinement import decompose_deviation, refine
from app.core.types import (
    ClosedLoopResult,
    HoldDecision,
    NewsSignal,
    Override,
    Outcome,
    ScoredInstrument,
)
from app.feature_scores import red_green_label, red_green_payload


TRADE_DATE = date(2026, 10, 22)


class FakeRankingStore:
    def __init__(self, rankings):
        self.rankings = list(rankings)
        self.saved_rankings = []
        self.saved_hold_decisions = []
        self.saved_outcomes = []
        self.saved_overrides = []

    def get_rankings(self, trade_date, statement_scope):
        return list(self.rankings)

    def save_ranking(self, ranking):
        self.saved_rankings.append(ranking)

    def save_hold_decision(self, decision):
        self.saved_hold_decisions.append(decision)

    def get_hold_decisions(self, trade_date):
        return []

    def get_latest_hold_decision(self, company_id, before_date):
        return None

    def save_outcome(self, outcome):
        self.saved_outcomes.append(outcome)

    def get_outcome(self, company_id, trade_date):
        return None

    def get_pending_outcomes(self):
        return []

    def save_override(self, override):
        self.saved_overrides.append(override)

    def get_applied_overrides(self, trade_date):
        return []


class FakeMarketData:
    def get_close_price(self, company_id, trade_date):
        return 100.0

    def get_forward_return(self, company_id, trade_date, horizon_days):
        return 0.01


class FakeNewsSource:
    def __init__(self, signals=None):
        self.signals = signals or []

    def get_signals(self, trade_date, company_id=None):
        return list(self.signals)


class FakeBacktest:
    def get_decile_stats(self, start_date, end_date):
        return [
            {
                "decile": 1,
                "observations": 20,
                "avg_5d": 0.05,
            },
        ]


def make_scored(**overrides) -> ScoredInstrument:
    defaults = dict(
        company_id=1,
        trade_date=TRADE_DATE,
        statement_scope="Consolidated",
        score=70.0,
        red_green="green",
        momentum_score=60.0,
        profitability_score=80.0,
        leverage_score=40.0,
        valuation_score=50.0,
        overall_rank=1,
        overall_percentile=0.9,
        valid_feature_count=4,
        valid_category_count=4,
    )
    defaults.update(overrides)
    return ScoredInstrument(**defaults)


# ---------------------------------------------------------------------
# Red/green mapping
# ---------------------------------------------------------------------

@pytest.mark.parametrize(
    ("score", "label"),
    [
        (None, "needs_data"),
        (10.0, "red"),
        (49.99, "red"),
        (50.0, "green"),
        (75.0, "green"),
        (100.0, "green"),
    ],
)
def test_red_green_label(score, label):
    assert red_green_label(score) == label


def test_red_green_payload():
    assert red_green_payload(None) == {"score": None, "red_green": "needs_data"}
    assert red_green_payload(30.0) == {"score": 30.0, "red_green": "red"}
    assert red_green_payload(80.0) == {"score": 80.0, "red_green": "green"}


# ---------------------------------------------------------------------
# Hold decision
# ---------------------------------------------------------------------

def test_decide_hold_missing_score_is_pending():
    decision = decide_hold(
        company_id=1,
        trade_date=TRADE_DATE,
        score=None,
    )

    assert decision.action == "pending"
    assert decision.red_green == "needs_data"
    assert decision.action_reason == "missing_score"


def test_decide_hold_red_score_holds():
    decision = decide_hold(
        company_id=1,
        trade_date=TRADE_DATE,
        score=30.0,
        close_price=100.0,
    )

    assert decision.action == "hold"
    assert decision.red_green == "red"
    assert decision.action_reason == "red_score"


def test_decide_hold_green_initial_hold_uses_application_duration():
    decision = decide_hold(
        company_id=1,
        trade_date=TRADE_DATE,
        score=70.0,
        close_price=100.0,
        hold_duration_days=DEFAULT_HOLD_DURATION_DAYS,
    )

    assert decision.action == "hold"
    assert decision.red_green == "green"
    assert decision.action_reason == "initial_hold"
    assert decision.hold_until == date(2026, 10, 24)


def test_decide_hold_green_sells_on_target():
    decision = decide_hold(
        company_id=1,
        trade_date=TRADE_DATE,
        score=70.0,
        close_price=105.0,
        sell_target_price=100.0,
        sell_target_date=date(2026, 10, 28),
    )

    assert decision.action == "sell"
    assert decision.action_reason == "target_achieved"


def test_decide_hold_green_sells_on_time_to_target():
    decision = decide_hold(
        company_id=1,
        trade_date=TRADE_DATE,
        score=70.0,
        close_price=100.0,
        sell_target_price=None,
        sell_target_date=date(2026, 10, 23),
        hold_duration_days=2,
    )

    assert decision.action == "sell"
    assert decision.action_reason == "time_to_target_reached"


# ---------------------------------------------------------------------
# Refinement
# ---------------------------------------------------------------------

def test_decompose_deviation_spreads_across_valid_categories():
    scored = make_scored()

    attribution = decompose_deviation(
        deviation=0.04,
        scored=scored,
    )

    total = sum(attribution.values())

    assert abs(total - 0.04) < 1e-9
    assert attribution["momentum"] > 0.0
    assert attribution["profitability"] > 0.0


def test_refine_recomputes_overall_score_from_attribution():
    scored = make_scored(score=70.0)

    attribution = decompose_deviation(
        deviation=0.04,
        scored=scored,
    )

    refined = refine(scored=scored, attribution=attribution)

    assert refined.score is not None
    assert refined.score != scored.score
    assert refined.score > 0.0


# ---------------------------------------------------------------------
# News override
# ---------------------------------------------------------------------

def test_news_override_significance_requires_backtest_support():
    assert (
        assess_significance(
            sentiment="positive",
            score_adjustment=5.0,
            backtest_stats=[{"decile": 1, "observations": 20, "avg_5d": 0.05}],
            overall_rank=1,
            overall_percentile=0.9,
        )
        == "confirmed"
    )

    assert (
        assess_significance(
            sentiment="neutral",
            score_adjustment=5.0,
            backtest_stats=[{"decile": 1, "observations": 20, "avg_5d": 0.05}],
            overall_rank=1,
            overall_percentile=0.9,
        )
        == "rejected"
    )

    assert (
        assess_significance(
            sentiment="positive",
            score_adjustment=5.0,
            backtest_stats=[],
            overall_rank=1,
            overall_percentile=0.9,
        )
        == "rejected"
    )


def test_news_override_significance_rejects_unset_placement():
    assert (
        assess_significance(
            sentiment="positive",
            score_adjustment=5.0,
            backtest_stats=[{"decile": 1, "observations": 20, "avg_5d": 0.05}],
        )
        == "rejected"
    )


def test_news_override_significance_uses_instruments_own_decile():
    # The instrument sits in decile 5; a decile 1 with healthy
    # observations elsewhere in the universe must not confirm the signal.
    assert (
        assess_significance(
            sentiment="positive",
            score_adjustment=5.0,
            backtest_stats=[
                {"decile": 1, "observations": 100, "avg_5d": 0.05},
                {"decile": 5, "observations": 2, "avg_5d": 0.05},
            ],
            overall_rank=45,
            overall_percentile=0.55,
        )
        == "rejected"
    )


def test_news_override_significance_rejects_zero_adjustment():
    assert (
        assess_significance(
            sentiment="positive",
            score_adjustment=0.0,
            backtest_stats=[{"decile": 1, "observations": 20, "avg_5d": 0.05}],
            overall_rank=1,
            overall_percentile=0.9,
        )
        == "rejected"
    )


def test_news_override_applies_adjustment():
    scored = make_scored(score=70.0)

    adjusted = apply_override(scored=scored, adjustment=5.0)

    assert adjusted.score == 75.0
    assert adjusted.red_green == "green"


# ---------------------------------------------------------------------
# Closed-loop engine
# ---------------------------------------------------------------------

def test_closed_loop_runs_score_hold_verify_refine_override():
    ranking_store = FakeRankingStore([make_scored()])

    result = run_closed_loop(
        TRADE_DATE,
        ranking_store=ranking_store,
        market_data=FakeMarketData(),
        news_source=FakeNewsSource(),
        backtest=FakeBacktest(),
    )

    assert len(result.scored) == 1
    assert len(result.hold_decisions) == 1
    assert result.hold_decisions[0].action == "hold"
    assert len(result.outcomes) == 1
    assert len(result.overrides) == 0

    assert len(ranking_store.saved_hold_decisions) == 1
    assert len(ranking_store.saved_outcomes) == 1
    assert len(ranking_store.saved_rankings) == 2


def test_closed_loop_persists_deviation_refinement():
    ranking_store = FakeRankingStore([make_scored()])

    result = run_closed_loop(
        TRADE_DATE,
        ranking_store=ranking_store,
        market_data=FakeMarketData(),
        news_source=FakeNewsSource(),
        backtest=FakeBacktest(),
    )

    outcome: Outcome = ranking_store.saved_outcomes[0]

    assert outcome.deviation is not None
    assert outcome.deviation > 0.0

    refined_ranking = ranking_store.saved_rankings[0]

    assert refined_ranking.score is not None
    assert refined_ranking.score > 0.0


def test_closed_loop_applies_news_override():
    ranking_store = FakeRankingStore([make_scored()])
    news_source = FakeNewsSource(
        signals=[
            NewsSignal(
                company_id=1,
                trade_date=TRADE_DATE,
                source="news_scanner",
                sentiment="positive",
                score_adjustment=5.0,
                significance="confirmed",
            )
        ]
    )

    result = run_closed_loop(
        TRADE_DATE,
        ranking_store=ranking_store,
        market_data=FakeMarketData(),
        news_source=news_source,
        backtest=FakeBacktest(),
    )

    assert len(result.overrides) == 1
    assert result.overrides[0].applied is True
    assert len(ranking_store.saved_overrides) == 1


def test_closed_loop_result_shape():
    result: ClosedLoopResult = ClosedLoopResult(
        trade_date=TRADE_DATE,
        scored=[],
        hold_decisions=[],
        outcomes=[],
        overrides=[],
    )

    assert result.trade_date == TRADE_DATE
