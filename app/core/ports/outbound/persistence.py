from __future__ import annotations

from datetime import date
from typing import Protocol, runtime_checkable

from app.core.types import HoldDecision, Outcome, Override, ScoredInstrument


@runtime_checkable
class RecommendationPersistencePort(Protocol):
    """Outbound port: persisted recommendation-loop state."""

    def get_rankings(
        self, trade_date: date, statement_scope: str
    ) -> list[ScoredInstrument]: ...

    def save_ranking(self, ranking: ScoredInstrument) -> None: ...

    def save_hold_decision(self, decision: HoldDecision) -> None: ...

    def get_hold_decisions(self, trade_date: date) -> list[HoldDecision]: ...

    def get_latest_hold_decision(
        self, company_id: int, before_date: date
    ) -> HoldDecision | None: ...

    def save_outcome(self, outcome: Outcome) -> None: ...

    def get_outcome(
        self, company_id: int, trade_date: date
    ) -> Outcome | None: ...

    def get_pending_outcomes(self) -> list[Outcome]: ...

    def save_override(self, override: Override) -> None: ...

    def get_applied_overrides(self, trade_date: date) -> list[Override]: ...
