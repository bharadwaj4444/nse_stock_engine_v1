from __future__ import annotations

from dataclasses import dataclass
from datetime import date


# Hold decision actions.
HOLD_ACTION_HOLD = "hold"
HOLD_ACTION_SELL = "sell"
HOLD_ACTION_PENDING = "pending"

# Outcome verification statuses.
OUTCOME_STATUS_PENDING = "pending"
OUTCOME_STATUS_VERIFIED = "verified"

# News sentiment values.
NEWS_SENTIMENT_POSITIVE = "positive"
NEWS_SENTIMENT_NEGATIVE = "negative"
NEWS_SENTIMENT_NEUTRAL = "neutral"

# Red/green presentation states.
RED_GREEN_RED = "red"
RED_GREEN_GREEN = "green"
RED_GREEN_NEEDS_DATA = "needs_data"


@dataclass(frozen=True)
class ScoredInstrument:
    """Red/green-scored instrument for one ranking cycle."""

    company_id: int
    trade_date: date
    statement_scope: str = "Consolidated"
    score: float | None = None
    red_green: str = RED_GREEN_NEEDS_DATA
    momentum_score: float | None = None
    profitability_score: float | None = None
    leverage_score: float | None = None
    valuation_score: float | None = None
    overall_rank: int | None = None
    overall_percentile: float | None = None
    valid_feature_count: int = 0
    valid_category_count: int = 0


@dataclass(frozen=True)
class HoldDecision:
    """Engine-decided hold / sell stance for one instrument."""

    company_id: int
    trade_date: date
    action: str = HOLD_ACTION_PENDING
    score: float | None = None
    red_green: str = RED_GREEN_NEEDS_DATA
    action_reason: str = "missing_score"
    hold_until: date | None = None
    sell_target_price: float | None = None
    sell_target_date: date | None = None
    expected_return: float | None = None


@dataclass(frozen=True)
class Outcome:
    """Verified outcome of a held instrument."""

    company_id: int
    trade_date: date
    expected_return: float | None = None
    actual_return: float | None = None
    deviation: float | None = None
    status: str = OUTCOME_STATUS_PENDING


@dataclass(frozen=True)
class NewsSignal:
    """News scanner override signal for one instrument."""

    company_id: int
    trade_date: date
    source: str = "news_scanner"
    sentiment: str = NEWS_SENTIMENT_NEUTRAL
    score_adjustment: float | None = None
    significance: str = "unknown"


@dataclass(frozen=True)
class Override:
    """News override applied (or rejected) during a ranking cycle."""

    company_id: int
    trade_date: date
    source: str
    sentiment: str
    original_score: float | None = None
    adjusted_score: float | None = None
    adjustment: float = 0.0
    significance_status: str = "unknown"
    applied: bool = False


@dataclass
class ClosedLoopResult:
    """Aggregated output of one closed-loop cycle."""

    trade_date: date
    scored: list[ScoredInstrument]
    hold_decisions: list[HoldDecision]
    outcomes: list[Outcome]
    overrides: list[Override]
