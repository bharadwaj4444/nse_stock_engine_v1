from __future__ import annotations

from datetime import date

from app.core.holds import DEFAULT_HOLD_DURATION_DAYS, decide_hold
from app.core.news_override import build_override
from app.core.outcomes import resolve_outcome
from app.core.refinement import decompose_deviation, refine
from app.core.types import (
    HOLD_ACTION_HOLD,
    RED_GREEN_GREEN,
    ClosedLoopResult,
    HoldDecision,
    NewsSignal,
    Override,
    Outcome,
    ScoredInstrument,
)
from app.core.ports.outbound import (
    BacktestPort,
    MarketDataPort,
    NewsSignalSourcePort,
    RecommendationPersistencePort,
)


def _to_scored(
    company_id: int,
    trade_date: date,
    *,
    score: float | None = None,
    red_green: str = "needs_data",
    momentum_score: float | None = None,
    profitability_score: float | None = None,
    leverage_score: float | None = None,
    valuation_score: float | None = None,
    overall_rank: int | None = None,
    overall_percentile: float | None = None,
    valid_feature_count: int = 0,
    valid_category_count: int = 0,
) -> ScoredInstrument:
    return ScoredInstrument(
        company_id=company_id,
        trade_date=trade_date,
        statement_scope="Consolidated",
        score=score,
        red_green=red_green,
        momentum_score=momentum_score,
        profitability_score=profitability_score,
        leverage_score=leverage_score,
        valuation_score=valuation_score,
        overall_rank=overall_rank,
        overall_percentile=overall_percentile,
        valid_feature_count=valid_feature_count,
        valid_category_count=valid_category_count,
    )


def _expected_return_from_decile(
    decile_stats: list[dict],
    overall_rank: int | None,
) -> float | None:
    if not decile_stats or overall_rank is None:
        return None

    decile = max(1, -(-int(overall_rank) // 10))

    for row in decile_stats:
        try:
            if int(row.get("decile") or 0) == decile:
                return float(row.get("avg_5d") or 0.0)
        except (TypeError, ValueError):
            continue

    return None


def run_closed_loop(
    trade_date: date,
    *,
    ranking_store: RecommendationPersistencePort,
    market_data: MarketDataPort,
    news_source: NewsSignalSourcePort,
    backtest: BacktestPort,
    hold_duration_days: int = DEFAULT_HOLD_DURATION_DAYS,
) -> ClosedLoopResult:
    """
    Run one closed-loop cycle:

        score -> hold -> verify -> refine -> override
    """

    scored: list[ScoredInstrument] = []
    hold_decisions: list[HoldDecision] = []
    outcomes: list[Outcome] = []
    overrides: list[Override] = []

    # --------------------------------------------------------
    # Stage 1: score
    # --------------------------------------------------------
    for ranking in ranking_store.get_rankings(
        trade_date=trade_date,
        statement_scope="Consolidated",
    ):
        scored.append(
            ScoredInstrument(
                company_id=ranking.company_id,
                trade_date=ranking.trade_date,
                statement_scope=ranking.statement_scope,
                score=ranking.score,
                red_green=ranking.red_green,
                momentum_score=ranking.momentum_score,
                profitability_score=ranking.profitability_score,
                leverage_score=ranking.leverage_score,
                valuation_score=ranking.valuation_score,
                overall_rank=ranking.overall_rank,
                overall_percentile=ranking.overall_percentile,
                valid_feature_count=ranking.valid_feature_count,
                valid_category_count=ranking.valid_category_count,
            )
        )

    # --------------------------------------------------------
    # Stage 2: hold
    # --------------------------------------------------------
    for instrument in scored:
        decision = decide_hold(
            instrument.company_id,
            trade_date,
            score=instrument.score,
            close_price=market_data.get_close_price(
                instrument.company_id,
                trade_date,
            ),
            sell_target_price=None,
            sell_target_date=None,
            hold_duration_days=hold_duration_days,
        )

        ranking_store.save_hold_decision(decision)
        hold_decisions.append(decision)

    # --------------------------------------------------------
    # Stage 3: verify outcomes against actual forward returns
    # --------------------------------------------------------
    scored_by_company = {
        instrument.company_id: instrument for instrument in scored
    }

    for decision in hold_decisions:
        if decision.action != HOLD_ACTION_HOLD:
            continue

        if decision.red_green != RED_GREEN_GREEN:
            continue

        instrument = scored_by_company.get(decision.company_id)

        actual_return = market_data.get_forward_return(
            decision.company_id,
            trade_date,
            hold_duration_days=hold_duration_days,
        )

        expected_return = decision.expected_return

        if expected_return is None and instrument is not None:
            decile_stats = backtest.get_decile_stats(
                start_date=trade_date,
                end_date=trade_date,
            )

            expected_return = _expected_return_from_decile(
                decile_stats=decile_stats,
                overall_rank=instrument.overall_rank,
            )

        outcome = resolve_outcome(
            company_id=decision.company_id,
            trade_date=trade_date,
            expected_return=expected_return,
            actual_return=actual_return,
        )

        ranking_store.save_outcome(outcome)
        outcomes.append(outcome)

    # --------------------------------------------------------
    # Stage 4: refine rankings from deviations
    # --------------------------------------------------------
    for outcome in outcomes:
        if outcome.deviation is None or outcome.deviation == 0.0:
            continue

        instrument = next(
            (
                item
                for item in scored
                if item.company_id == outcome.company_id
            ),
            None,
        )

        if instrument is None:
            continue

        attribution = decompose_deviation(
            deviation=outcome.deviation,
            scored=instrument,
        )

        # AD-3: persist prior calculation state before derived mutation.
        ranking_store.save_ranking(instrument)

        refined = refine(scored=instrument, attribution=attribution)

        ranking_store.save_ranking(refined)

    # --------------------------------------------------------
    # Stage 5: news override
    # --------------------------------------------------------
    signals: list[NewsSignal] = news_source.get_signals(
        trade_date=trade_date
    )

    for signal in signals:
        instrument = next(
            (
                item
                for item in scored
                if item.company_id == signal.company_id
            ),
            None,
        )

        override = build_override(
            scored=(
                instrument
                if instrument is not None
                else _to_scored(
                    signal.company_id,
                    trade_date,
                    score=None,
                )
            ),
            source=signal.source,
            sentiment=signal.sentiment,
            score_adjustment=signal.score_adjustment,
            backtest_stats=backtest.get_decile_stats(
                start_date=trade_date,
                end_date=trade_date,
            ),
        )

        ranking_store.save_override(override)
        overrides.append(override)

    return ClosedLoopResult(
        trade_date=trade_date,
        scored=scored,
        hold_decisions=hold_decisions,
        outcomes=outcomes,
        overrides=overrides,
    )
