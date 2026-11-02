from __future__ import annotations

from datetime import date, timedelta

from app.core.types import (
    HOLD_ACTION_HOLD,
    HOLD_ACTION_PENDING,
    HOLD_ACTION_SELL,
    RED_GREEN_GREEN,
    RED_GREEN_NEEDS_DATA,
    RED_GREEN_RED,
    HoldDecision,
)
from app.feature_scores import RED_GREEN_THRESHOLD, red_green_label


DEFAULT_HOLD_DURATION_DAYS = 2


def decide_hold(
    company_id: int,
    trade_date: date,
    *,
    score: float | None = None,
    close_price: float | None = None,
    sell_target_price: float | None = None,
    sell_target_date: date | None = None,
    hold_duration_days: int = DEFAULT_HOLD_DURATION_DAYS,
) -> HoldDecision:
    """
    Decide the engine-held stance for one scored instrument.

    Hold duration is decided by the application (V1 default window:
    1-3 days), not fixed by a global horizon. The engine sells when the
    specific target is achieved or the time-to-target is reached; it
    holds otherwise. Unknown / insufficient state resolves to a pending
    hold.
    """

    red_green = red_green_label(score)

    if score is None:
        return HoldDecision(
            company_id=company_id,
            trade_date=trade_date,
            action=HOLD_ACTION_PENDING,
            score=None,
            red_green=RED_GREEN_NEEDS_DATA,
            action_reason="missing_score",
        )

    if score < RED_GREEN_THRESHOLD:
        return HoldDecision(
            company_id=company_id,
            trade_date=trade_date,
            action=HOLD_ACTION_HOLD,
            score=score,
            red_green=RED_GREEN_RED,
            action_reason="red_score",
        )

    # Green score: the engine decides hold vs sell.
    hold_until = trade_date + timedelta(days=hold_duration_days)

    if sell_target_price is not None and close_price is not None:
        if close_price >= sell_target_price:
            return HoldDecision(
                company_id=company_id,
                trade_date=trade_date,
                action=HOLD_ACTION_SELL,
                score=score,
                red_green=RED_GREEN_GREEN,
                action_reason="target_achieved",
                hold_until=hold_until,
                sell_target_price=sell_target_price,
                sell_target_date=sell_target_date,
            )

    if sell_target_date is not None and hold_until >= sell_target_date:
        return HoldDecision(
            company_id=company_id,
            trade_date=trade_date,
            action=HOLD_ACTION_SELL,
            score=score,
            red_green=RED_GREEN_GREEN,
            action_reason="time_to_target_reached",
            hold_until=hold_until,
            sell_target_price=sell_target_price,
            sell_target_date=sell_target_date,
        )

    return HoldDecision(
        company_id=company_id,
        trade_date=trade_date,
        action=HOLD_ACTION_HOLD,
        score=score,
        red_green=RED_GREEN_GREEN,
        action_reason="initial_hold",
        hold_until=hold_until,
        sell_target_price=sell_target_price,
        sell_target_date=sell_target_date,
    )
