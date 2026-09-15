from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime
from typing import Any, Iterable

from sqlalchemy.orm import Session

from database.models.cdas_booking import CdasBookingFailure, CdasBookingOpportunity
from services.cdas_opportunity_pipeline import pipeline_stage_for_item

FAILURE_REASONS: tuple[tuple[str, str], ...] = (
    ("capacity_unavailable", "Insufficient CDAS capacity"),
    ("booking_window_closed", "Booking window unavailable"),
    ("cdas_rejected", "CDAS / payroll rejected booking"),
    ("employer_payroll_issue", "Employer / payroll issue"),
    ("invalid_or_missing_documents", "Invalid or missing documents"),
    ("client_unreachable", "Client unreachable"),
    ("client_declined", "Client declined"),
    ("duplicate_or_existing_booking", "Duplicate or existing booking"),
    ("system_or_submission_error", "System or submission error"),
    ("other", "Other"),
)
FAILURE_REASON_IDS = {value for value, _ in FAILURE_REASONS}
FAILURE_REASON_LABELS = dict(FAILURE_REASONS)


def normalize_failure_reason(value: str) -> str:
    reason = str(value or "").strip().lower()
    if reason not in FAILURE_REASON_IDS:
        raise ValueError("Unsupported CDAS booking failure reason")
    return reason


def serialize_failure(row: CdasBookingFailure) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "opportunity_id": str(row.opportunity_id),
        "reason_code": row.reason_code,
        "reason_label": FAILURE_REASON_LABELS.get(row.reason_code, row.reason_code.replace("_", " ").title()),
        "reason_details": row.reason_details,
        "failed_at": row.failed_at,
        "retry_eligible": bool(row.retry_eligible),
        "retry_after": row.retry_after,
        "created_by_user_id": str(row.created_by_user_id) if row.created_by_user_id else None,
        "created_at": row.created_at,
    }


def retry_is_due(failure: CdasBookingFailure | dict[str, Any], *, now: datetime) -> bool:
    if isinstance(failure, dict):
        eligible = bool(failure.get("retry_eligible"))
        retry_after = failure.get("retry_after")
    else:
        eligible = bool(failure.retry_eligible)
        retry_after = failure.retry_after
    return bool(eligible and (retry_after is None or retry_after <= now))


def record_booking_failure(
    db: Session,
    *,
    item: CdasBookingOpportunity,
    company_id,
    user_id,
    reason_code: str,
    reason_details: str | None,
    failed_at: datetime,
    retry_eligible: bool,
    retry_after: datetime | None,
) -> CdasBookingFailure:
    current_stage = pipeline_stage_for_item(item)
    if current_stage == "booked" or item.status == "booked":
        raise ValueError("Booked CDAS opportunities are terminal and cannot be failed")
    if current_stage == "failed":
        raise ValueError("This opportunity is already failed; reopen it before recording another failure")
    reason = normalize_failure_reason(reason_code)
    if retry_after is not None and retry_after < failed_at:
        raise ValueError("Retry time cannot be before the failure time")
    if not retry_eligible and retry_after is not None:
        raise ValueError("A retry time can only be set when retry is allowed")

    failure = CdasBookingFailure(
        company_id=company_id,
        opportunity_id=item.id,
        reason_code=reason,
        reason_details=(reason_details or "").strip() or None,
        failed_at=failed_at,
        retry_eligible=retry_eligible,
        retry_after=retry_after,
        created_by_user_id=user_id,
    )
    db.add(failure)
    item.pipeline_stage = "failed"
    item.pipeline_updated_at = failed_at
    item.pipeline_updated_by_user_id = user_id
    item.status = "monitoring"
    db.commit()
    db.refresh(failure)
    db.refresh(item)
    return failure


def reopen_failed_opportunity(
    db: Session,
    *,
    item: CdasBookingOpportunity,
    latest_failure: CdasBookingFailure | None,
    user_id,
    now: datetime,
) -> CdasBookingOpportunity:
    if pipeline_stage_for_item(item) != "failed":
        raise ValueError("Only failed CDAS opportunities can be reopened")
    if latest_failure is None:
        raise ValueError("No booking failure record exists for this opportunity")
    if not latest_failure.retry_eligible:
        raise ValueError("The latest failure is not marked retryable")
    if latest_failure.retry_after is not None and latest_failure.retry_after > now:
        raise ValueError("The retry date has not been reached yet")

    item.pipeline_stage = "identified"
    item.pipeline_updated_at = now
    item.pipeline_updated_by_user_id = user_id
    item.status = "monitoring"
    db.commit()
    db.refresh(item)
    return item


def build_failure_workspace(
    opportunities: Iterable[dict[str, Any]],
    failures: Iterable[CdasBookingFailure],
    *,
    now: datetime,
) -> dict[str, Any]:
    source_opportunities = [dict(value) for value in opportunities]
    histories: dict[str, list[dict[str, Any]]] = defaultdict(list)
    all_failures: list[dict[str, Any]] = []
    for row in failures:
        serialized = serialize_failure(row)
        histories[str(row.opportunity_id)].append(serialized)
        all_failures.append(serialized)

    for values in histories.values():
        values.sort(key=lambda value: str(value.get("failed_at") or ""), reverse=True)

    items: list[dict[str, Any]] = []
    for source in source_opportunities:
        item = dict(source)
        history = histories.get(str(item.get("id") or ""), [])
        latest = history[0] if history else None
        item.update(
            {
                "failure_count": len(history),
                "latest_failure": latest,
                "failure_history": history,
                "retry_due": bool(latest and retry_is_due(latest, now=now)),
            }
        )
        if history or str(item.get("pipeline_stage") or "").lower() == "failed":
            items.append(item)

    items.sort(
        key=lambda item: (
            0 if item.get("retry_due") else 1,
            -int(item.get("failure_count") or 0),
            str((item.get("latest_failure") or {}).get("failed_at") or ""),
        )
    )
    reason_counts = Counter(str(value.get("reason_code") or "other") for value in all_failures)
    current_failed = [item for item in items if str(item.get("pipeline_stage") or "").lower() == "failed"]
    recordable = [
        item
        for item in source_opportunities
        if str(item.get("pipeline_stage") or "").lower() not in {"failed", "booked"}
        and str(item.get("state") or "").upper() != "BOOKED"
    ]

    return {
        "as_of": now,
        "summary": {
            "failure_attempts": len(all_failures),
            "currently_failed": len(current_failed),
            "retryable": sum(1 for item in current_failed if bool((item.get("latest_failure") or {}).get("retry_eligible"))),
            "retry_due": sum(1 for item in current_failed if item.get("retry_due")),
            "non_retryable": sum(1 for item in current_failed if item.get("latest_failure") and not bool(item["latest_failure"].get("retry_eligible"))),
        },
        "reason_counts": [
            {"reason_code": code, "reason_label": label, "count": int(reason_counts.get(code, 0))}
            for code, label in FAILURE_REASONS
            if reason_counts.get(code, 0)
        ],
        "reason_options": [
            {"value": code, "label": label}
            for code, label in FAILURE_REASONS
        ],
        "recordable_opportunities": recordable,
        "items": items,
        "total": len(items),
    }
