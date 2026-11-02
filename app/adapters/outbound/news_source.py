from __future__ import annotations

from datetime import date

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.ports.outbound import NewsSignalSourcePort
from app.core.types import NewsSignal


class NewsSignalSourceAdapter(NewsSignalSourcePort):
    """Outbound adapter implementing the news signal source port."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def get_signals(
        self, trade_date: date, company_id: int | None = None
    ) -> list[NewsSignal]:
        sql = text(
            """
            SELECT
                company_id,
                trade_date,
                source,
                sentiment,
                score_adjustment,
                significance
            FROM news_signals
            WHERE trade_date = :trade_date
            """
        )

        params: dict = {"trade_date": trade_date}

        if company_id is not None:
            sql = text(
                """
                SELECT
                    company_id,
                    trade_date,
                    source,
                    sentiment,
                    score_adjustment,
                    significance
                FROM news_signals
                WHERE trade_date = :trade_date
                  AND company_id = :company_id
                """
            )
            params["company_id"] = company_id

        rows = (
            self.session.execute(sql, params)
            .mappings()
            .all()
        )

        signals: list[NewsSignal] = []

        for row in rows:
            score_adjustment = (
                float(row["score_adjustment"])
                if row["score_adjustment"] is not None
                else None
            )

            signals.append(
                NewsSignal(
                    company_id=int(row["company_id"]),
                    trade_date=row["trade_date"],
                    source=row["source"],
                    sentiment=row["sentiment"],
                    score_adjustment=score_adjustment,
                    significance=row["significance"],
                )
            )

        return signals
