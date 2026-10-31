from datetime import date, datetime, timezone
from typing import TYPE_CHECKING

from app.db import SessionLocal
from app.models import VerificationRun, VerificationResult
from sqlalchemy import select

if TYPE_CHECKING:
    from app.verification import CheckResult


def save_verification_run(
    target_date: date,
    results: list["CheckResult"],
    trigger: str,
    started_at: datetime,
    completed_at: datetime,
) -> int:
    if trigger not in {"analyze", "verify"}:
        raise ValueError(f"Invalid verification trigger: {trigger}")

    failures = sum(r.status == "FAIL" for r in results)
    warnings = sum(r.status == "WARN" for r in results)

    run = VerificationRun(
        trade_date=target_date,
        trigger=trigger,
        started_at=started_at,
        completed_at=completed_at,
        failure_count=failures,
        warning_count=warnings,
        check_count=len(results),
        results=[
            VerificationResult(
                check_name=result.name,
                status=result.status,
                expected=result.expected,
                actual=result.actual,
                details=result.details or "",
            )
            for result in results
        ],
    )

    # Parent and all check results are committed atomically.
    with SessionLocal() as session:
        with session.begin():
            session.add(run)
            session.flush()
            run_id = run.id

    return run_id

def get_verification_history(
    target_date: date | None = None,
    limit: int = 20,
) -> list[VerificationRun]:
    """Return recent verification runs, optionally filtered by trade date."""
    if limit < 1:
        raise ValueError("limit must be at least 1")

    stmt = select(VerificationRun)

    if target_date is not None:
        stmt = stmt.where(VerificationRun.trade_date == target_date)

    stmt = stmt.order_by(
        VerificationRun.started_at.desc(),
        VerificationRun.id.desc(),
    ).limit(limit)

    with SessionLocal() as session:
        return session.execute(stmt).scalars().all()


def get_verification_run_details(
    run_id: int,
) -> tuple[VerificationRun | None, list[VerificationResult]]:
    """Return one verification run and its individual check results."""
    with SessionLocal() as session:
        run = session.get(VerificationRun, run_id)

        if run is None:
            return None, []

        stmt = (
            select(VerificationResult)
            .where(VerificationResult.run_id == run_id)
            .order_by(VerificationResult.check_name)
        )

        results = session.execute(stmt).scalars().all()

        return run, results

def compare_verification_results(
    older_results: list[VerificationResult],
    newer_results: list[VerificationResult],
) -> dict:
    """Compare verification checks from two runs."""

    older_by_name = {
        result.check_name: result
        for result in older_results
    }

    newer_by_name = {
        result.check_name: result
        for result in newer_results
    }

    older_names = set(older_by_name)
    newer_names = set(newer_by_name)

    added = [
        newer_by_name[name]
        for name in sorted(newer_names - older_names)
    ]

    removed = [
        older_by_name[name]
        for name in sorted(older_names - newer_names)
    ]

    changed = []
    unchanged = []

    for name in sorted(older_names & newer_names):
        older = older_by_name[name]
        newer = newer_by_name[name]

        differences = []

        if older.status != newer.status:
            differences.append("status")

        if older.expected != newer.expected:
            differences.append("expected")

        if older.actual != newer.actual:
            differences.append("actual")

        if differences:
            changed.append({
                "check_name": name,
                "differences": differences,
                "older": older,
                "newer": newer,
            })
        else:
            unchanged.append(newer)

    return {
        "changed": changed,
        "added": added,
        "removed": removed,
        "unchanged": unchanged,
    }

def compare_verification_runs(
    older_run_id: int,
    newer_run_id: int,
) -> tuple[VerificationRun, VerificationRun, dict] | None:
    """Compare the check results of two saved verification runs."""

    if older_run_id == newer_run_id:
        raise ValueError("Older and newer run IDs must be different")

    older_run, older_results = get_verification_run_details(older_run_id)
    newer_run, newer_results = get_verification_run_details(newer_run_id)

    if older_run is None or newer_run is None:
        return None

    comparison = compare_verification_results(
        older_results,
        newer_results,
    )

    return older_run, newer_run, comparison