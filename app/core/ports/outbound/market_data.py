from __future__ import annotations

from datetime import date
from typing import Protocol, runtime_checkable


@runtime_checkable
class MarketDataPort(Protocol):
    """Outbound port: market data needed to resolve outcomes."""

    def get_close_price(
        self, company_id: int, trade_date: date
    ) -> float | None: ...

    def get_forward_return(
        self, company_id: int, trade_date: date, horizon_days: int
    ) -> float | None: ...
