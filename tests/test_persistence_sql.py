from __future__ import annotations

from datetime import date
from decimal import Decimal
import uuid

import pytest
from sqlalchemy import delete, text

from app.adapters.outbound.persistence import RecommendationPersistenceAdapter
from app.core.types import HoldDecision, Outcome, Override, ScoredInstrument
from app.db import SessionLocal
from app.models import Company


TEST_TRADE_DATE = date(2030, 5, 7)
TEST_SCOPE = "Consolidated"


def _create_company() -> int:
    symbol = f"TEST_ADAPTER_{uuid.uuid4().hex[:12].upper()}"

    with SessionLocal.begin() as db:
        company = Company(
            nse_symbol=symbol,
            company_name="Adapter SQL Test Company",
            status="TEST",
            is_active=False,
        )
        db.add(company)
        db.flush()
        return company.id


def _insert_stock_ranking(
    company_id,
    *,
    overall_score=70.0,
    overall_rank=1,
    overall_percentile=0.9,
):
    with SessionLocal.begin() as db:
        db.execute(
            text(
                """
                INSERT INTO stock_rankings (
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
                    valid_category_count,
                    calculation_method,
                    created_at,
                    updated_at
                )
                VALUES (
                    :company_id,
                    :trade_date,
                    :scope,
                    60.0, 80.0, 40.0, 50.0,
                    :overall_score,
                    :overall_rank,
                    :overall_percentile,
                    4, 4,
                    'TEST_ADAPTER_SQL',
                    CURRENT_TIMESTAMP,
                    CURRENT_TIMESTAMP
                )
                """
            ),
            {
                "company_id": company_id,
                "trade_date": TEST_TRADE_DATE,
                "scope": TEST_SCOPE,
                "overall_score": overall_score,
                "overall_rank": overall_rank,
                "overall_percentile": overall_percentile,
            },
        )


def _cleanup(company_id):
    with SessionLocal.begin() as db:
        for table in (
            "overrides",
            "outcomes",
            "hold_decisions",
            "stock_rankings",
        ):
            db.execute(
                text(
                    f"DELETE FROM {table} WHERE company_id = :company_id"
                ),
                {"company_id": company_id},
            )

        db.execute(
            delete(Company).where(Company.id == company_id)
        )


def test_adapter_reads_and_writes_rankings_round_trip():
    company_id = _create_company()

    try:
        _insert_stock_ranking(company_id)

        with SessionLocal() as session:
            adapter = RecommendationPersistenceAdapter(session)

            scored = adapter.get_rankings(
                trade_date=TEST_TRADE_DATE,
                statement_scope=TEST_SCOPE,
            )

        assert len(scored) == 1

        instrument = scored[0]

        assert instrument.company_id == company_id
        assert instrument.score == pytest.approx(70.0)
        assert instrument.red_green == "green"
        assert instrument.overall_rank == 1
        assert instrument.overall_percentile == pytest.approx(0.9)
        assert instrument.momentum_score == pytest.approx(60.0)

        adjusted = ScoredInstrument(
            company_id=instrument.company_id,
            trade_date=instrument.trade_date,
            statement_scope=instrument.statement_scope,
            score=80.0,
            red_green="green",
            momentum_score=75.0,
            profitability_score=80.0,
            leverage_score=40.0,
            valuation_score=50.0,
            overall_rank=instrument.overall_rank,
            overall_percentile=instrument.overall_percentile,
            valid_feature_count=4,
            valid_category_count=4,
        )

        with SessionLocal() as session:
            adapter = RecommendationPersistenceAdapter(session)
            adapter.save_ranking(adjusted)

        with SessionLocal() as session:
            rows = session.execute(
                text(
                    """
                    SELECT overall_score, momentum_score,
                           overall_rank, overall_percentile
                    FROM stock_rankings
                    WHERE company_id = :company_id
                      AND trade_date = :trade_date
                      AND statement_scope = :scope
                    """
                ),
                {
                    "company_id": company_id,
                    "trade_date": TEST_TRADE_DATE,
                    "scope": TEST_SCOPE,
                },
            ).mappings().all()

        assert len(rows) == 1
        assert float(rows[0]["overall_score"]) == pytest.approx(80.0)
        assert float(rows[0]["momentum_score"]) == pytest.approx(75.0)
        # The nightly rebuild owns rank/percentile; save_ranking must
        # not silently rewrite them.
        assert rows[0]["overall_rank"] == 1
        assert float(rows[0]["overall_percentile"]) == pytest.approx(0.9)
    finally:
        _cleanup(company_id)


def test_adapter_hold_decisions_round_trip_upsert():
    company_id = _create_company()

    try:
        with SessionLocal() as session:
            adapter = RecommendationPersistenceAdapter(session)

            adapter.save_hold_decision(
                HoldDecision(
                    company_id=company_id,
                    trade_date=TEST_TRADE_DATE,
                    action="hold",
                    score=70.0,
                    red_green="green",
                    action_reason="initial_hold",
                    hold_until=date(2026, 10, 24),
                )
            )
            adapter.save_hold_decision(
                HoldDecision(
                    company_id=company_id,
                    trade_date=TEST_TRADE_DATE,
                    action="sell",
                    score=70.0,
                    red_green="green",
                    action_reason="time_to_target_reached",
                    hold_until=date(2026, 10, 24),
                    sell_target_date=date(2026, 10, 24),
                )
            )

            decisions = adapter.get_hold_decisions(trade_date=TEST_TRADE_DATE)

        assert len(decisions) == 1
        assert decisions[0].action == "sell"
        assert decisions[0].action_reason == "time_to_target_reached"
        assert decisions[0].sell_target_date == date(2026, 10, 24)

        with SessionLocal() as session:
            adapter = RecommendationPersistenceAdapter(session)
            prior = adapter.get_latest_hold_decision(
                company_id,
                before_date=date(2030, 5, 8),
            )

        assert prior is not None
        assert prior.hold_until == date(2026, 10, 24)
    finally:
        _cleanup(company_id)


def test_adapter_outcomes_round_trip_and_pending_listing():
    company_id = _create_company()

    try:
        with SessionLocal() as session:
            adapter = RecommendationPersistenceAdapter(session)

            adapter.save_outcome(
                Outcome(
                    company_id=company_id,
                    trade_date=TEST_TRADE_DATE,
                    expected_return=0.05,
                    actual_return=None,
                    deviation=None,
                    status="pending",
                )
            )

            outcome = adapter.get_outcome(
                company_id,
                TEST_TRADE_DATE,
            )

            assert outcome is not None
            assert outcome.status == "pending"
            assert outcome.expected_return == pytest.approx(0.05)

            pending = adapter.get_pending_outcomes()

            assert any(
                item.company_id == company_id
                and item.trade_date == TEST_TRADE_DATE
                for item in pending
            )

            adapter.save_outcome(
                Outcome(
                    company_id=company_id,
                    trade_date=TEST_TRADE_DATE,
                    expected_return=0.05,
                    actual_return=0.01,
                    deviation=0.04,
                    status="verified",
                )
            )

            verified = adapter.get_outcome(company_id, TEST_TRADE_DATE)

            assert verified is not None
            assert verified.status == "verified"
            assert verified.deviation == pytest.approx(0.04)

            pending_after = adapter.get_pending_outcomes()

            assert not any(
                item.company_id == company_id
                and item.trade_date == TEST_TRADE_DATE
                for item in pending_after
            )
    finally:
        _cleanup(company_id)


def test_adapter_overrides_round_trip_and_applied_filter():
    company_id = _create_company()

    try:
        with SessionLocal() as session:
            adapter = RecommendationPersistenceAdapter(session)

            adapter.save_override(
                Override(
                    company_id=company_id,
                    trade_date=date(2026, 10, 21),
                    source="news_scanner",
                    sentiment="positive",
                    original_score=70.0,
                    adjusted_score=75.0,
                    adjustment=5.0,
                    significance_status="confirmed",
                    applied=True,
                )
            )
            adapter.save_override(
                Override(
                    company_id=company_id,
                    trade_date=date(2026, 10, 22),
                    source="news_scanner",
                    sentiment="negative",
                    original_score=70.0,
                    adjusted_score=70.0,
                    adjustment=0.0,
                    significance_status="rejected",
                    applied=False,
                )
            )

            applied = adapter.get_applied_overrides(
                trade_date=TEST_TRADE_DATE,
            )

        applicable = [
            override
            for override in applied
            if override.company_id == company_id
        ]

        assert len(applicable) == 1
        assert applicable[0].adjustment == pytest.approx(5.0)
        assert applicable[0].applied is True
    finally:
        _cleanup(company_id)
