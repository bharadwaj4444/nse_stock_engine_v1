from datetime import date, datetime, timezone
from typing import TYPE_CHECKING

from app.db import SessionLocal
from app.models import VerificationRun, VerificationResult

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