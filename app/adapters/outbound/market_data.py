from __future__ import annotations

from datetime import date

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.ports.outbound import MarketDataPort
from app.core.horizons import horizon_bucket


class MarketDataAdapter(MarketDataPort):
    """Outbound adapter implementing the market data port."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def get_close_price(
        self, company_id: int, trade_date: date
    ) -> float | None:
        sql = text(
            """
            SELECT close_price
            FROM daily_prices
            WHERE company_id = :company_id
              AND trade_date = :trade_date
            """
        )

        return (
            self.session.execute(
                sql,
                {"company_id": company_id, "trade_date": trade_date},
            )
            .scalar_one_or_none()
        )

    def get_forward_return(
        self,
        company_id: int,
        trade_date: date,
        horizon_days: int,
    ) -> float | None:
        bucket_days = horizon_bucket(horizon_days)

        column = (
            f"forward_{bucket_days}d_return"
        )

        sql = text(
            f"""
            SELECT {column}
            FROM future_returns
            WHERE company_id = :company_id
              AND trade_date = :trade_date
            """
        )

        return (
            self.session.execute(
                sql,
                {"company_id": company_id, "trade_date": trade_date},
            )
            .scalar_one_or_none()
        )
