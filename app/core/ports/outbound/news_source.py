from __future__ import annotations

from datetime import date
from typing import Protocol, runtime_checkable

from app.core.types import NewsSignal


@runtime_checkable
class NewsSignalSourcePort(Protocol):
    """Outbound port: news scanner signals for a cycle."""

    def get_signals(
        self, trade_date: date, company_id: int | None = None
    ) -> list[NewsSignal]: ...
