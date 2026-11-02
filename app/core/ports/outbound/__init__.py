from __future__ import annotations

from app.core.ports.outbound.backtest import BacktestPort
from app.core.ports.outbound.market_data import MarketDataPort
from app.core.ports.outbound.news_source import NewsSignalSourcePort
from app.core.ports.outbound.persistence import RecommendationPersistencePort


__all__ = [
    "BacktestPort",
    "MarketDataPort",
    "NewsSignalSourcePort",
    "RecommendationPersistencePort",
]
