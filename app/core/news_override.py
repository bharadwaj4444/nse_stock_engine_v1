from __future__ import annotations

from app.core.deciles import decile_for_rank
from app.core.types import (
    NEWS_SENTIMENT_NEGATIVE,
    NEWS_SENTIMENT_POSITIVE,
    Override,
    ScoredInstrument,
    NewsSignal,
)


MIN_OVERRIDE_SIGNIFICANCE_OBSERVATIONS = 10
MIN_OVERRIDE_SCORE_ADJUSTMENT = 0.0


def assess_significance(
    sentiment: str,
    score_adjustment: float | None,
    backtest_stats: list[dict] | None = None,
    overall_rank: int | None = None,
    overall_percentile: float | None = None,
) -> str:
    """
    Backtrack a news override to verify the significance of the news type.

    V1 rule: a sentiment override is only actionable when it carries a
    meaningful score adjustment and the backtest evidence for the
    decile containing the instrument meets the observation floor.

    Note: the store carries no news-type-specific history, so decile-level
    evidence for the instrument's own cohort is the strongest backtest
    signal available. Summing all deciles' observations would accept
    ten unrelated datapoints as confirmation.
    """

    if sentiment not in (NEWS_SENTIMENT_POSITIVE, NEWS_SENTIMENT_NEGATIVE):
        return "rejected"

    if score_adjustment is None or abs(score_adjustment) <= MIN_OVERRIDE_SCORE_ADJUSTMENT:
        return "rejected"

    stats_by_decile: dict[int, dict] = {}

    for row in backtest_stats or []:
        try:
            stats_by_decile[int(row.get("decile") or 0)] = row
        except (TypeError, ValueError):
            continue

    decile = decile_for_rank(overall_rank, overall_percentile)

    if decile is None:
        return "rejected"

    row = stats_by_decile.get(decile)

    try:
        observations = int(row.get("observations") or 0) if row else 0
    except (TypeError, ValueError):
        observations = 0

    if observations < MIN_OVERRIDE_SIGNIFICANCE_OBSERVATIONS:
        return "rejected"

    return "confirmed"


def apply_override(
    scored: ScoredInstrument,
    adjustment: float,
) -> ScoredInstrument:
    """
    Apply a news override adjustment to the scored instrument.

    Positive news adds confidence, negative news reduces it; the
    adjusted score feeds subsequent ranking cycles.
    """

    if scored.score is None:
        return scored

    adjusted_score = scored.score + adjustment

    if adjusted_score < 0.0:
        adjusted_score = 0.0

    if adjusted_score > 100.0:
        adjusted_score = 100.0

    red_green = "green" if adjusted_score >= 50.0 else "red"

    return ScoredInstrument(
        company_id=scored.company_id,
        trade_date=scored.trade_date,
        statement_scope=scored.statement_scope,
        score=adjusted_score,
        red_green=red_green,
        momentum_score=scored.momentum_score,
        profitability_score=scored.profitability_score,
        leverage_score=scored.leverage_score,
        valuation_score=scored.valuation_score,
        overall_rank=scored.overall_rank,
        overall_percentile=scored.overall_percentile,
        valid_feature_count=scored.valid_feature_count,
        valid_category_count=scored.valid_category_count,
    )


def build_override(
    scored: ScoredInstrument,
    source: str,
    sentiment: str,
    score_adjustment: float | None,
    backtest_stats: list[dict] | None = None,
) -> Override:
    significance_status = assess_significance(
        sentiment=sentiment,
        score_adjustment=score_adjustment,
        backtest_stats=backtest_stats,
        overall_rank=scored.overall_rank,
        overall_percentile=scored.overall_percentile,
    )

    original_score = scored.score

    applied = (
        significance_status == "confirmed"
        and original_score is not None
        and score_adjustment is not None
    )

    adjusted_score = (
        apply_override(scored, score_adjustment).score
        if applied
        else original_score
    )

    return Override(
        company_id=scored.company_id,
        trade_date=scored.trade_date,
        source=source,
        sentiment=sentiment,
        original_score=original_score,
        adjusted_score=adjusted_score,
        adjustment=score_adjustment or 0.0,
        significance_status=significance_status,
        applied=applied,
    )
