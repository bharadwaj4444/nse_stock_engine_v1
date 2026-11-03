from __future__ import annotations

from datetime import date

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.types import (
    HoldDecision,
    Outcome,
    Override,
    ScoredInstrument,
)
from app.core.ports.outbound import RecommendationPersistencePort
from app.feature_scores import red_green_label


class RecommendationPersistenceAdapter(
    RecommendationPersistencePort,
):
    """Outbound adapter implementing the recommendation persistence port."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def get_rankings(
        self, trade_date: date, statement_scope: str
    ) -> list[ScoredInstrument]:
        sql = text(
            """
            SELECT
                company_id,
                trade_date,
                statement_scope,
                momentum_score,
                profitability_score,
                leverage_score,
                valuation_score,
                overall_score,
                overall_rank,
                overall_percentile,
                valid_feature_count,
                valid_category_count
            FROM stock_rankings
            WHERE trade_date = :trade_date
              AND statement_scope = :statement_scope
            """
        )

        rows = (
            self.session.execute(
                sql,
                {"trade_date": trade_date, "statement_scope": statement_scope},
            )
            .mappings()
            .all()
        )

        scored: list[ScoredInstrument] = []

        for row in rows:
            score = row["overall_score"]

            scored.append(
                ScoredInstrument(
                    company_id=int(row["company_id"]),
                    trade_date=row["trade_date"],
                    statement_scope=row["statement_scope"],
                    score=float(score) if score is not None else None,
                    red_green=red_green_label(
                        float(score) if score is not None else None
                    ),
                    momentum_score=(
                        float(row["momentum_score"])
                        if row["momentum_score"] is not None
                        else None
                    ),
                    profitability_score=(
                        float(row["profitability_score"])
                        if row["profitability_score"] is not None
                        else None
                    ),
                    leverage_score=(
                        float(row["leverage_score"])
                        if row["leverage_score"] is not None
                        else None
                    ),
                    valuation_score=(
                        float(row["valuation_score"])
                        if row["valuation_score"] is not None
                        else None
                    ),
                    overall_rank=(
                        int(row["overall_rank"])
                        if row["overall_rank"] is not None
                        else None
                    ),
                    overall_percentile=(
                        float(row["overall_percentile"])
                        if row["overall_percentile"] is not None
                        else None
                    ),
                    valid_feature_count=int(row["valid_feature_count"]),
                    valid_category_count=int(row["valid_category_count"]),
                )
            )

        return scored

    def save_ranking(self, ranking: ScoredInstrument) -> None:
        self.session.execute(
            text(
                """
                UPDATE stock_rankings
                SET
                    momentum_score = :momentum_score,
                    profitability_score = :profitability_score,
                    leverage_score = :leverage_score,
                    valuation_score = :valuation_score,
                    overall_score = :overall_score,
                    updated_at = CURRENT_TIMESTAMP
                WHERE company_id = :company_id
                  AND trade_date = :trade_date
                  AND statement_scope = :statement_scope
                """
            ),
            {
                "company_id": ranking.company_id,
                "trade_date": ranking.trade_date,
                "statement_scope": ranking.statement_scope,
                "momentum_score": ranking.momentum_score,
                "profitability_score": ranking.profitability_score,
                "leverage_score": ranking.leverage_score,
                "valuation_score": ranking.valuation_score,
                "overall_score": ranking.score,
            },
        )

        self.session.commit()

    def save_hold_decision(self, decision: HoldDecision) -> None:
        self.session.execute(
            text(
                """
                INSERT INTO hold_decisions (
                    company_id,
                    trade_date,
                    action,
                    score,
                    red_green,
                    action_reason,
                    hold_until,
                    sell_target_price,
                    sell_target_date,
                    expected_return,
                    created_at,
                    updated_at
                )
                VALUES (
                    :company_id,
                    :trade_date,
                    :action,
                    :score,
                    :red_green,
                    :action_reason,
                    :hold_until,
                    :sell_target_price,
                    :sell_target_date,
                    :expected_return,
                    CURRENT_TIMESTAMP,
                    CURRENT_TIMESTAMP
                )
                ON CONFLICT (company_id, trade_date)
                DO UPDATE SET
                    action = EXCLUDED.action,
                    score = EXCLUDED.score,
                    red_green = EXCLUDED.red_green,
                    action_reason = EXCLUDED.action_reason,
                    hold_until = EXCLUDED.hold_until,
                    sell_target_price = EXCLUDED.sell_target_price,
                    sell_target_date = EXCLUDED.sell_target_date,
                    expected_return = EXCLUDED.expected_return,
                    updated_at = CURRENT_TIMESTAMP
                """
            ),
            {
                "company_id": decision.company_id,
                "trade_date": decision.trade_date,
                "action": decision.action,
                "score": decision.score,
                "red_green": decision.red_green,
                "action_reason": decision.action_reason,
                "hold_until": decision.hold_until,
                "sell_target_price": decision.sell_target_price,
                "sell_target_date": decision.sell_target_date,
                "expected_return": decision.expected_return,
            },
        )

        self.session.commit()

    def _map_hold_decision(self, row) -> HoldDecision:
        return HoldDecision(
            company_id=int(row["company_id"]),
            trade_date=row["trade_date"],
            action=row["action"],
            score=float(row["score"]) if row["score"] is not None else None,
            red_green=row["red_green"],
            action_reason=row["action_reason"],
            hold_until=row["hold_until"],
            sell_target_price=(
                float(row["sell_target_price"])
                if row["sell_target_price"] is not None
                else None
            ),
            sell_target_date=row["sell_target_date"],
            expected_return=(
                float(row["expected_return"])
                if row["expected_return"] is not None
                else None
            ),
        )

    @staticmethod
    def _map_outcome(row) -> Outcome:
        return Outcome(
            company_id=int(row["company_id"]),
            trade_date=row["trade_date"],
            expected_return=(
                float(row["expected_return"])
                if row["expected_return"] is not None
                else None
            ),
            actual_return=(
                float(row["actual_return"])
                if row["actual_return"] is not None
                else None
            ),
            deviation=(
                float(row["deviation"])
                if row["deviation"] is not None
                else None
            ),
            status=row["status"],
        )

    @staticmethod
    def _map_override(row) -> Override:
        return Override(
            company_id=int(row["company_id"]),
            trade_date=row["trade_date"],
            source=row["source"],
            sentiment=row["sentiment"],
            original_score=(
                float(row["original_score"])
                if row["original_score"] is not None
                else None
            ),
            adjusted_score=(
                float(row["adjusted_score"])
                if row["adjusted_score"] is not None
                else None
            ),
            adjustment=(
                float(row["adjustment"])
                if row["adjustment"] is not None
                else 0.0
            ),
            significance_status=row["significance_status"],
            applied=bool(row["applied"]),
        )

    def get_latest_hold_decision(
        self, company_id: int, before_date: date
    ) -> HoldDecision | None:
        sql = text(
            """
            SELECT
                company_id,
                trade_date,
                action,
                score,
                red_green,
                action_reason,
                hold_until,
                sell_target_price,
                sell_target_date,
                expected_return
            FROM hold_decisions
            WHERE company_id = :company_id
              AND trade_date < :before_date
            ORDER BY trade_date DESC
            LIMIT 1
            """
        )

        row = (
            self.session.execute(
                sql,
                {
                    "company_id": company_id,
                    "before_date": before_date,
                },
            )
            .mappings()
            .first()
        )

        return self._map_hold_decision(row) if row is not None else None

    def get_outcome(
        self, company_id: int, trade_date: date
    ) -> Outcome | None:
        sql = text(
            """
            SELECT
                company_id,
                trade_date,
                expected_return,
                actual_return,
                deviation,
                status
            FROM outcomes
            WHERE company_id = :company_id
              AND trade_date = :trade_date
            """
        )

        row = (
            self.session.execute(
                sql,
                {
                    "company_id": company_id,
                    "trade_date": trade_date,
                },
            )
            .mappings()
            .first()
        )

        return self._map_outcome(row) if row is not None else None

    def get_pending_outcomes(self) -> list[Outcome]:
        sql = text(
            """
            SELECT
                company_id,
                trade_date,
                expected_return,
                actual_return,
                deviation,
                status
            FROM outcomes
            WHERE status = 'pending'
            ORDER BY trade_date
            """
        )

        rows = (
            self.session.execute(sql)
            .mappings()
            .all()
        )

        return [self._map_outcome(row) for row in rows]

    def get_applied_overrides(self, trade_date: date) -> list[Override]:
        sql = text(
            """
            SELECT
                company_id,
                trade_date,
                source,
                sentiment,
                original_score,
                adjusted_score,
                adjustment,
                significance_status,
                applied
            FROM overrides
            WHERE applied
              AND trade_date <= :trade_date
            ORDER BY trade_date
            """
        )

        rows = (
            self.session.execute(
                sql,
                {"trade_date": trade_date},
            )
            .mappings()
            .all()
        )

        return [self._map_override(row) for row in rows]

    def get_hold_decisions(self, trade_date: date) -> list[HoldDecision]:
        sql = text(
            """
            SELECT
                company_id,
                trade_date,
                action,
                score,
                red_green,
                action_reason,
                hold_until,
                sell_target_price,
                sell_target_date,
                expected_return
            FROM hold_decisions
            WHERE trade_date = :trade_date
            """
        )

        rows = (
            self.session.execute(
                sql, {"trade_date": trade_date}
            )
            .mappings()
            .all()
        )

        return [self._map_hold_decision(row) for row in rows]

    def save_outcome(self, outcome: Outcome) -> None:
        self.session.execute(
            text(
                """
                INSERT INTO outcomes (
                    company_id,
                    trade_date,
                    expected_return,
                    actual_return,
                    deviation,
                    status,
                    created_at,
                    updated_at
                )
                VALUES (
                    :company_id,
                    :trade_date,
                    :expected_return,
                    :actual_return,
                    :deviation,
                    :status,
                    CURRENT_TIMESTAMP,
                    CURRENT_TIMESTAMP
                )
                ON CONFLICT (company_id, trade_date)
                DO UPDATE SET
                    expected_return = EXCLUDED.expected_return,
                    actual_return = EXCLUDED.actual_return,
                    deviation = EXCLUDED.deviation,
                    status = EXCLUDED.status,
                    updated_at = CURRENT_TIMESTAMP
                """
            ),
            {
                "company_id": outcome.company_id,
                "trade_date": outcome.trade_date,
                "expected_return": outcome.expected_return,
                "actual_return": outcome.actual_return,
                "deviation": outcome.deviation,
                "status": outcome.status,
            },
        )

        self.session.commit()

    def save_override(self, override: Override) -> None:
        self.session.execute(
            text(
                """
                INSERT INTO overrides (
                    company_id,
                    trade_date,
                    source,
                    sentiment,
                    original_score,
                    adjusted_score,
                    adjustment,
                    significance_status,
                    applied,
                    created_at,
                    updated_at
                )
                VALUES (
                    :company_id,
                    :trade_date,
                    :source,
                    :sentiment,
                    :original_score,
                    :adjusted_score,
                    :adjustment,
                    :significance_status,
                    :applied,
                    CURRENT_TIMESTAMP,
                    CURRENT_TIMESTAMP
                )
                ON CONFLICT (company_id, trade_date, source)
                DO UPDATE SET
                    sentiment = EXCLUDED.sentiment,
                    original_score = EXCLUDED.original_score,
                    adjusted_score = EXCLUDED.adjusted_score,
                    adjustment = EXCLUDED.adjustment,
                    significance_status = EXCLUDED.significance_status,
                    applied = EXCLUDED.applied,
                    updated_at = CURRENT_TIMESTAMP
                """
            ),
            {
                "company_id": override.company_id,
                "trade_date": override.trade_date,
                "source": override.source,
                "sentiment": override.sentiment,
                "original_score": override.original_score,
                "adjusted_score": override.adjusted_score,
                "adjustment": override.adjustment,
                "significance_status": override.significance_status,
                "applied": override.applied,
            },
        )

        self.session.commit()
