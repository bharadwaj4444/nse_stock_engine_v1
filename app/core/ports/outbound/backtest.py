from __future__ import annotations

from datetime import date
from typing import Protocol, runtime_checkable


@runtime_checkable
class BacktestPort(Protocol):
    """Outbound port: historical backtest evidence."""

    def get_decile_stats(
        self, start_date: date, end_date: date
    ) -> list[dict]: ...
