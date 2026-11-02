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

    def save_outcome(self, outcome: Outcome) -> None: ...

    def save_override(self, override: Override) -> None: ...
