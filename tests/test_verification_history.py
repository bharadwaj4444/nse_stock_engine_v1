from datetime import date, datetime, timezone

from app.models import VerificationRun, VerificationResult
from app.verification import CheckResult
from app.verification_history import save_verification_run
from sqlalchemy import delete, select
import pytest
from sqlalchemy.exc import IntegrityError

from app.db import SessionLocal


def test_save_verification_run(monkeypatch):
    target_date = date(2026, 10, 22)
    started_at = datetime.now(timezone.utc)
    completed_at = datetime.now(timezone.utc)

    results = [
        CheckResult(
            status="PASS",
            name="Daily price input",
            actual=2591,
        ),
        CheckResult(
            status="WARN",
            name="Quarterly cash-flow coverage",
            expected=100,
            actual=90,
            details="10 incomplete quarters",
        ),
        CheckResult(
            status="FAIL",
            name="Stock rankings coverage",
            expected=2591,
            actual=2500,
        ),
    ]

    saved = {}

    class FakeSession:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            return False

        def begin(self):
            return self

        def __enter_transaction__(self):
            return self

        def __exit_transaction__(self, exc_type, exc_val, exc_tb):
            return False

        def add(self, run):
            saved["run"] = run

        def flush(self):
            saved["run"].id = 123

    class FakeTransaction:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            return False

    session = FakeSession()
    session.begin = lambda: FakeTransaction()

    class FakeSessionFactory:
        def __call__(self):
            return session

    monkeypatch.setattr(
        "app.verification_history.SessionLocal",
        FakeSessionFactory(),
    )

    run_id = save_verification_run(
        target_date,
        results,
        "analyze",
        started_at,
        completed_at,
    )

    run = saved["run"]

    assert run_id == 123
    assert isinstance(run, VerificationRun)
    assert run.trade_date == target_date
    assert run.trigger == "analyze"
    assert run.failure_count == 1
    assert run.warning_count == 1
    assert run.check_count == 3

    assert len(run.results) == 3
    assert all(isinstance(r, VerificationResult) for r in run.results)
    assert [r.status for r in run.results] == ["PASS", "WARN", "FAIL"]

def test_multiple_verification_runs_persist_in_postgres():
    target_date = date(2099, 12, 31)
    timestamp = datetime.now(timezone.utc)

    first_id = None
    second_id = None

    try:
        first_id = save_verification_run(
            target_date=target_date,
            results=[
                CheckResult(status="PASS", name="Price coverage"),
                CheckResult(status="WARN", name="Cash-flow coverage"),
            ],
            trigger="analyze",
            started_at=timestamp,
            completed_at=timestamp,
        )

        second_id = save_verification_run(
            target_date=target_date,
            results=[
                CheckResult(status="PASS", name="Price coverage"),
                CheckResult(status="PASS", name="Cash-flow coverage"),
            ],
            trigger="verify",
            started_at=timestamp,
            completed_at=timestamp,
        )

        with SessionLocal() as session:
            runs = session.execute(
                select(VerificationRun)
                .where(VerificationRun.id.in_([first_id, second_id]))
                .order_by(VerificationRun.id)
            ).scalars().all()

            assert len(runs) == 2
            assert [run.trigger for run in runs] == ["analyze", "verify"]
            assert [run.check_count for run in runs] == [2, 2]
            assert [run.warning_count for run in runs] == [1, 0]

            result_counts = [
                len(run.results)
                for run in runs
            ]
            assert result_counts == [2, 2]

    finally:
        ids = [run_id for run_id in (first_id, second_id) if run_id]

        if ids:
            with SessionLocal.begin() as session:
                session.execute(
                    delete(VerificationRun).where(
                        VerificationRun.id.in_(ids)
                    )
                )

def test_failed_verification_save_rolls_back_entire_run():
    target_date = date(2099, 12, 30)
    timestamp = datetime.now(timezone.utc)

    with pytest.raises(IntegrityError):
        save_verification_run(
            target_date=target_date,
            results=[
                CheckResult(status="PASS", name="Duplicate check"),
                CheckResult(status="FAIL", name="Duplicate check"),
            ],
            trigger="analyze",
            started_at=timestamp,
            completed_at=timestamp,
        )

    with SessionLocal() as session:
        remaining = session.execute(
            select(VerificationRun).where(
                VerificationRun.trade_date == target_date,
                VerificationRun.started_at == timestamp,
            )
        ).scalars().all()

        assert remaining == []