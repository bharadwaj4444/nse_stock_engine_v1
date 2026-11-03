from __future__ import annotations

from app.core.types import ScoredInstrument
from app.feature_scores import red_green_label


CATEGORY_WEIGHTS = {
    "momentum": 0.30,
    "profitability": 0.30,
    "leverage": 0.15,
    "valuation": 0.25,
}

CATEGORY_ORDER = (
    "momentum",
    "profitability",
    "leverage",
    "valuation",
)


def _clamp_score(value: float) -> float:
    return max(0.0, min(100.0, value))


def _category_score(
    scored: ScoredInstrument, category: str
) -> float | None:
    if category == "momentum":
        return scored.momentum_score
    if category == "profitability":
        return scored.profitability_score
    if category == "leverage":
        return scored.leverage_score
    if category == "valuation":
        return scored.valuation_score
    return None


def _valid_categories(scored: ScoredInstrument) -> list[str]:
    return [
        category
        for category in CATEGORY_ORDER
        if _category_score(scored, category) is not None
    ]


def decompose_deviation(
    deviation: float,
    scored: ScoredInstrument,
) -> dict[str, float]:
    """
    Decompose a verification deviation into contributing signal
    categories.

    The deviation is spread across the valid categories in proportion to
    their composite weights (V1_CATEGORY_WEIGHTED_NORMALIZED).
    """

    valid = _valid_categories(scored)

    total_weight = sum(
        CATEGORY_WEIGHTS[category] for category in valid
    )

    attribution: dict[str, float] = {}

    for category in valid:
        weight = CATEGORY_WEIGHTS[category]
        attribution[category] = (
            deviation * weight / total_weight
            if total_weight > 0
            else 0.0
        )

    return attribution


def refine(
    scored: ScoredInstrument,
    attribution: dict[str, float],
) -> ScoredInstrument:
    """
    Refine a ranking from decomposed deviations.

    Adjusted category scores are recombined into a refined overall
    score using the V1 category weighted normalized composite.
    """

    adjusted_scores = dict(
        momentum=scored.momentum_score,
        profitability=scored.profitability_score,
        leverage=scored.leverage_score,
        valuation=scored.valuation_score,
    )

    for category, delta in attribution.items():
        current = _category_score(scored, category)
        adjusted_scores[category] = (
            _clamp_score(current + delta) if current is not None else current
        )

    valid = [
        category
        for category in CATEGORY_ORDER
        if adjusted_scores[category] is not None
    ]

    total_weight = sum(CATEGORY_WEIGHTS[category] for category in valid)

    if len(valid) == 0 or total_weight <= 0:
        return ScoredInstrument(
            company_id=scored.company_id,
            trade_date=scored.trade_date,
            statement_scope=scored.statement_scope,
            score=scored.score,
            red_green=scored.red_green,
            momentum_score=scored.momentum_score,
            profitability_score=scored.profitability_score,
            leverage_score=scored.leverage_score,
            valuation_score=scored.valuation_score,
            overall_rank=None,
            overall_percentile=None,
            valid_feature_count=scored.valid_feature_count,
            valid_category_count=scored.valid_category_count,
        )

    weighted_sum = sum(
        CATEGORY_WEIGHTS[category] * adjusted_scores[category]
        for category in valid
    )

    overall_score = _clamp_score(weighted_sum / total_weight)

    refined = ScoredInstrument(
        company_id=scored.company_id,
        trade_date=scored.trade_date,
        statement_scope=scored.statement_scope,
        score=overall_score,
        red_green=red_green_label(overall_score),
        momentum_score=adjusted_scores["momentum"],
        profitability_score=adjusted_scores["profitability"],
        leverage_score=adjusted_scores["leverage"],
        valuation_score=adjusted_scores["valuation"],
        overall_rank=None,
        overall_percentile=None,
        valid_feature_count=scored.valid_feature_count,
        valid_category_count=scored.valid_category_count,
    )

    return refined
