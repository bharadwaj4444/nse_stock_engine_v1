from __future__ import annotations

from datetime import date

from app.core.holds import DEFAULT_HOLD_DURATION_DAYS, decide_hold
from app.core.news_override import apply_override, build_override
from app.core.outcomes import resolve_outcome
from app.core.refinement import decompose_deviation, refine
from app.core.deciles import decile_for_rank
from app.core.horizons import horizon_bucket
from app.feature_scores import red_green_label
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


def _clamp_score(value: float) -> float:
    return max(0.0, min(100.0, value))


def _expected_return_from_decile(
    decile_stats: list[dict],
    overall_rank: int | None,
    overall_percentile: float | None,
    hold_duration_days: int,
) -> float | None:
    if not decile_stats:
        return None

    decile = decile_for_rank(overall_rank, overall_percentile)

    if decile is None:
        return None

    bucket = horizon_bucket(hold_duration_days)
    key = f"avg_{bucket}d"

    for row in decile_stats:
        try:
            if int(row.get("decile") or 0) == decile:
                value = row.get(key)
                return float(value) if value is not None else None
        except (TypeError, ValueError):
            continue

    return None


def _overlay_applied_overrides(
    scored: list[ScoredInstrument],
    ranking_store: RecommendationPersistencePort,
    trade_date: date,
) -> list[ScoredInstrument]:
    """
    Replay applied news overrides onto freshly read rankings.

    Rankings are rebuilt from raw state each cycle, which discards prior
    adjustments, so the applied override deltas (kept in the overrides
    table) are re-applied deterministically on every cycle. AD-3: the
    pre-mutation ranking is persisted before the overlaid score is.
    """

    applied = ranking_store.get_applied_overrides(trade_date)

    deltas: dict[int, float] = {}

    for override in applied:
        if not override.applied:
            continue
        if override.adjustment is None or override.adjustment == 0.0:
            continue
        deltas[override.company_id] = (
            deltas.get(override.company_id, 0.0) + float(override.adjustment)
        )

    if not deltas:
        return scored

    overlaid: list[ScoredInstrument] = []

    for instrument in scored:
        adjustment = deltas.get(instrument.company_id)

        if adjustment is None or instrument.score is None:
            overlaid.append(instrument)
            continue

        adjusted_score = _clamp_score(float(instrument.score) + adjustment)

        adjusted = ScoredInstrument(
            company_id=instrument.company_id,
            trade_date=instrument.trade_date,
            statement_scope=instrument.statement_scope,
            score=adjusted_score,
            red_green=red_green_label(adjusted_score),
            momentum_score=instrument.momentum_score,
            profitability_score=instrument.profitability_score,
            leverage_score=instrument.leverage_score,
            valuation_score=instrument.valuation_score,
            overall_rank=instrument.overall_rank,
            overall_percentile=instrument.overall_percentile,
            valid_feature_count=instrument.valid_feature_count,
            valid_category_count=instrument.valid_category_count,
        )

        ranking_store.save_ranking(instrument)
        ranking_store.save_ranking(adjusted)

        overlaid.append(adjusted)

    return overlaid


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
    prior_outcomes: dict[tuple[int, date], Outcome | None] = {}
    prior_instruments: dict[tuple[int, date], ScoredInstrument] = {}
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

    scored = _overlay_applied_overrides(scored, ranking_store, trade_date)

    # --------------------------------------------------------
    # Stage 2: hold
    # --------------------------------------------------------
    for instrument in scored:
        if instrument.red_green == RED_GREEN_GREEN:
            prior = ranking_store.get_latest_hold_decision(
                instrument.company_id,
                before_date=trade_date,
            )
            prior_target_price = (
                prior.sell_target_price if prior is not None else None
            )
            prior_target_date = (
                (prior.sell_target_date or prior.hold_until)
                if prior is not None
                else None
            )
        else:
            prior_target_price = None
            prior_target_date = None

        decision = decide_hold(
            instrument.company_id,
            trade_date,
            score=instrument.score,
            close_price=market_data.get_close_price(
                instrument.company_id,
                trade_date,
            ),
            sell_target_price=prior_target_price,
            sell_target_date=prior_target_date,
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

    def resolve(
        company_id: int,
        trade_date_: date,
        expected_return: float | None,
        actual_return: float | None,
        prior_outcome: Outcome | None,
    ) -> None:
        existing = (
            ranking_store.get_outcome(company_id, trade_date_)
            if prior_outcome is None
            else prior_outcome
        )

        outcome = resolve_outcome(
            company_id=company_id,
            trade_date=trade_date_,
            expected_return=expected_return,
            actual_return=actual_return,
        )

        ranking_store.save_outcome(outcome)
        outcomes.append(outcome)
        prior_outcomes[(company_id, trade_date_)] = existing

    for decision in hold_decisions:
        if decision.action != HOLD_ACTION_HOLD:
            continue

        if decision.red_green != RED_GREEN_GREEN:
            continue

        instrument = scored_by_company.get(decision.company_id)

        actual_return = market_data.get_forward_return(
            decision.company_id,
            trade_date,
            horizon_days=hold_duration_days,
        )

        expected_return = decision.expected_return

        if expected_return is None and instrument is not None:
            decile_stats = backtest.get_decile_stats(
                start_date=trade_date,
                end_date=trade_date,
            )

            expected_return = _expected_return_from_decile(
                decile_stats,
                overall_rank=instrument.overall_rank,
                overall_percentile=instrument.overall_percentile,
                hold_duration_days=hold_duration_days,
            )

        resolve(
            decision.company_id,
            trade_date,
            expected_return=expected_return,
            actual_return=actual_return,
            prior_outcome=None,
        )

    # Pending outcomes from prior cycles: resolve once forward-return
    # data has arrived. The horizon is recovered from the original hold
    # decision; expected return falls back to that date's decile stats.
    for pending in ranking_store.get_pending_outcomes():
        if (pending.company_id, pending.trade_date) in prior_outcomes:
            continue

        prior_decisions = ranking_store.get_hold_decisions(pending.trade_date)
        prior_decision = next(
            (
                decision
                for decision in prior_decisions
                if decision.company_id == pending.company_id
            ),
            None,
        )

        if (
            prior_decision is not None
            and prior_decision.hold_until is not None
        ):
            horizon = max(
                1,
                (prior_decision.hold_until - pending.trade_date).days,
            )
        else:
            horizon = DEFAULT_HOLD_DURATION_DAYS

        prior_ranking = next(
            (
                ranking
                for ranking in ranking_store.get_rankings(
                    trade_date=pending.trade_date,
                    statement_scope="Consolidated",
                )
                if ranking.company_id == pending.company_id
            ),
            None,
        )

        if prior_ranking is not None:
            prior_instruments[
                (prior_ranking.company_id, prior_ranking.trade_date)
            ] = prior_ranking

        expected_return = pending.expected_return

        if expected_return is None:
            prior_rank = (
                prior_ranking.overall_rank if prior_ranking is not None else None
            )
            prior_percentile = (
                prior_ranking.overall_percentile
                if prior_ranking is not None
                else None
            )

            decile_stats = backtest.get_decile_stats(
                start_date=pending.trade_date,
                end_date=pending.trade_date,
            )

            expected_return = _expected_return_from_decile(
                decile_stats,
                overall_rank=prior_rank,
                overall_percentile=prior_percentile,
                hold_duration_days=horizon,
            )

        actual_return = market_data.get_forward_return(
            pending.company_id,
            pending.trade_date,
            horizon_days=horizon,
        )

        if actual_return is None and expected_return is None:
            # Still unresolvable; leave the pending outcome untouched.
            continue

        resolve(
            pending.company_id,
            pending.trade_date,
            expected_return=expected_return,
            actual_return=actual_return,
            prior_outcome=pending,
        )

    # --------------------------------------------------------
    # Stage 4: refine rankings from deviations
    # --------------------------------------------------------
    for outcome in outcomes:
        if outcome.deviation is None or outcome.deviation == 0.0:
            continue

        existing = prior_outcomes.get((outcome.company_id, outcome.trade_date))

        if existing is not None and existing.deviation is not None:
            try:
                if abs(
                    float(existing.deviation) - float(outcome.deviation)
                ) < 1e-12:
                    # Already refined for this deviation; rerunning must
                    # not refine twice.
                    continue
            except (TypeError, ValueError):
                pass

        instrument = prior_instruments.get(
            (outcome.company_id, outcome.trade_date)
        )

        if instrument is None:
            instrument = next(
                (
                    item
                    for item in scored
                    if item.company_id == outcome.company_id
                    and item.trade_date == outcome.trade_date
                ),
                None,
            )

        if instrument is None:
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

        if (
            override.applied
            and override.adjustment is not None
            and instrument is not None
            and instrument.score is not None
        ):
            # Persist the adjusted score so delivery reflects the
            # override. The stage-1 overlay re-derives the same value
            # on the next cycle from the raw ranking plus override deltas.
            adjusted_instrument = apply_override(instrument, override.adjustment)
            ranking_store.save_ranking(instrument)
            ranking_store.save_ranking(adjusted_instrument)

    return ClosedLoopResult(
        trade_date=trade_date,
        scored=scored,
        hold_decisions=hold_decisions,
        outcomes=outcomes,
        overrides=overrides,
    )
