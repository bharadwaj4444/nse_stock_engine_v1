from __future__ import annotations

from datetime import date

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.ports.outbound import BacktestPort


class BacktestAdapter(BacktestPort):
    """Outbound adapter implementing the backtest port."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def get_decile_stats(
        self, start_date: date, end_date: date
    ) -> list[dict]:
        from app.backtest import run_decile_backtest

        with self.session.begin():
            rows = run_decile_backtest(
                start_date=start_date,
                end_date=end_date,
                session=self.session,
            )

        return [dict(row) for row in rows]
