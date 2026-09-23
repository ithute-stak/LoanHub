from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from database.models.cdas_official import CdasDailyIntelligenceRun
from database.models.client_loan_company import ClientCompanyLoan
from database.models.enums import LoanStatus
from database.models.lending_operations import CDASPayrollProfile


_ELIGIBLE_LOAN_STATUSES = {LoanStatus.ACTIVE, LoanStatus.DEFAULTED}
_STALE_RUNNING_SECONDS = 60 * 60


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def list_daily_intelligence_company_ids(db: Session) -> list[UUID]:
    """Companies that actually have exact-ID verified payroll debt to monitor."""
    rows = (
        db.query(CDASPayrollProfile.company_id)
        .join(
            ClientCompanyLoan,
            (ClientCompanyLoan.company_id == CDASPayrollProfile.company_id)
            & (ClientCompanyLoan.borrower_id == CDASPayrollProfile.borrower_id),
        )
        .filter(
            CDASPayrollProfile.verified.is_(True),
            ClientCompanyLoan.status.in_(_ELIGIBLE_LOAN_STATUSES),
            ClientCompanyLoan.balance > 0,
        )
        .distinct()
        .order_by(CDASPayrollProfile.company_id)
        .all()
    )
    return [row[0] for row in rows]


def claim_daily_intelligence_run(
    db: Session,
    *,
    company_id: UUID,
    run_date: date,
    timezone_name: str,
    scheduled_time: str = "03:45",
    max_profiles: int = 100,
) -> CdasDailyIntelligenceRun | None:
    """Atomically claim a company/day before any provider request is made.

    The database uniqueness constraint is the final concurrency authority. A
    process restart, duplicate maintenance replica or overlapping tick receives
    the existing claim instead of consuming CDAS quota twice.
    """
    row = CdasDailyIntelligenceRun(
        company_id=company_id,
        run_date=run_date,
        timezone=timezone_name,
        scheduled_time=scheduled_time,
        status="running",
        started_at=_utcnow(),
        max_profiles=max(1, int(max_profiles)),
        eligible_profiles=0,
        checked_profiles=0,
        ready_profiles=0,
        no_capacity_profiles=0,
        issue_count=0,
        provider_writes=0,
        summary={},
    )
    db.add(row)
    try:
        db.commit()
        db.refresh(row)
        return row
    except IntegrityError:
        db.rollback()
        return None


def complete_daily_intelligence_run(
    db: Session,
    *,
    run: CdasDailyIntelligenceRun,
    outcome: dict[str, Any],
) -> CdasDailyIntelligenceRun:
    issues = max(0, int(outcome.get("failures") or 0))
    provider_writes = max(0, int(outcome.get("provider_writes") or 0))
    if provider_writes != 0:
        # This job has a strict read-only provider contract. Surface a hard
        # health issue if that invariant is ever violated by future code.
        issues += 1

    run.status = "completed" if issues == 0 else "completed_with_issues"
    run.completed_at = _utcnow()
    run.eligible_profiles = max(0, int(outcome.get("eligible_profiles") or 0))
    run.checked_profiles = max(0, int(outcome.get("checked") or 0))
    run.ready_profiles = max(0, int(outcome.get("ready_for_collection_review") or 0))
    run.no_capacity_profiles = max(0, int(outcome.get("monitor_no_capacity") or 0))
    run.issue_count = issues
    run.provider_writes = provider_writes
    run.error_message = None
    run.summary = dict(outcome)
    db.commit()
    db.refresh(run)
    return run


def fail_daily_intelligence_run(
    db: Session,
    *,
    run: CdasDailyIntelligenceRun,
    message: str = "Daily CDAS intelligence run did not complete.",
) -> CdasDailyIntelligenceRun:
    run.status = "failed"
    run.completed_at = _utcnow()
    run.issue_count = max(1, int(run.issue_count or 0))
    run.provider_writes = 0
    run.error_message = str(message or "Daily CDAS intelligence run did not complete.")[:1000]
    db.commit()
    db.refresh(run)
    return run


def latest_daily_intelligence_run(
    db: Session,
    *,
    company_id: UUID,
) -> CdasDailyIntelligenceRun | None:
    return (
        db.query(CdasDailyIntelligenceRun)
        .filter(CdasDailyIntelligenceRun.company_id == company_id)
        .order_by(CdasDailyIntelligenceRun.run_date.desc(), CdasDailyIntelligenceRun.started_at.desc())
        .first()
    )


def serialize_daily_intelligence_run(
    run: CdasDailyIntelligenceRun | None,
    *,
    timezone_name: str,
    scheduled_time: str = "03:45",
) -> dict[str, Any]:
    if run is None:
        return {
            "schedule": scheduled_time,
            "timezone": timezone_name,
            "status": "not_run",
            "health": "awaiting_first_run",
            "healthy": True,
            "run_date": None,
            "started_at": None,
            "completed_at": None,
            "eligible_profiles": 0,
            "checked_profiles": 0,
            "ready_profiles": 0,
            "no_capacity_profiles": 0,
            "issue_count": 0,
            "provider_writes": 0,
            "message": "Daily CDAS monitoring is scheduled for 03:45. No completed company run is recorded yet.",
        }

    status = str(run.status or "running")
    if status == "completed":
        health = "healthy"
        healthy = True
        message = "The latest scheduled CDAS monitoring run completed normally."
    elif status == "running":
        started_at = run.started_at
        stale = bool(started_at and (_utcnow() - started_at).total_seconds() > _STALE_RUNNING_SECONDS)
        if stale:
            health = "needs_intervention"
            healthy = False
            message = "The latest CDAS monitoring run has remained in progress for over one hour. Review the maintenance worker before any manual retry."
        else:
            health = "running"
            healthy = True
            message = "The scheduled CDAS monitoring run is currently in progress."
    elif status == "completed_with_issues":
        health = "needs_review"
        healthy = False
        message = "The latest CDAS monitoring run completed, but one or more records need review."
    else:
        health = "needs_intervention"
        healthy = False
        message = run.error_message or "The latest CDAS monitoring run needs intervention."

    return {
        "schedule": run.scheduled_time or scheduled_time,
        "timezone": run.timezone or timezone_name,
        "status": status,
        "health": health,
        "healthy": healthy,
        "run_date": run.run_date.isoformat() if run.run_date else None,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
        "eligible_profiles": int(run.eligible_profiles or 0),
        "checked_profiles": int(run.checked_profiles or 0),
        "ready_profiles": int(run.ready_profiles or 0),
        "no_capacity_profiles": int(run.no_capacity_profiles or 0),
        "issue_count": int(run.issue_count or 0),
        "provider_writes": int(run.provider_writes or 0),
        "message": message,
    }
