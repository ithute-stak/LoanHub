"""CDAS bulk orchestration rules; no provider calls or background worker."""
from __future__ import annotations
import hashlib
import json
from decimal import Decimal
from typing import Iterable

# The only allowed transitions while bulk CDAS execution is disabled.
ALLOWED_TRANSITIONS = {
    "draft": {"cancelled"},
    "cancelled": set(),
}


def batch_fingerprint(employees: Iterable) -> str:
    """Canonical hash binds idempotency to the exact borrower, employee and instalment set."""
    rows = []
    for item in employees:
        number = str(item.employee_number).strip().casefold()
        amount = Decimal(str(item.proposed_monthly_installment)).quantize(Decimal("0.01"))
        if not number or not amount.is_finite() or amount <= 0:
            raise ValueError("Invalid bulk candidate")
        rows.append((str(item.borrower_id), number, str(amount)))
    rows.sort()
    return hashlib.sha256(
        json.dumps(rows, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    ).hexdigest()


def transition_batch(current_status: str, desired_status: str) -> str:
    """Prevents starting or resuming provider execution until explicitly enabled."""
    if desired_status not in ALLOWED_TRANSITIONS.get(current_status, set()):
        raise ValueError("Bulk job transition is disabled or invalid")
    return desired_status


def safe_batch_summary(batch, items: list) -> dict:
    """No salary, national ID, provider credentials or unreviewed raw payloads."""
    return {
        "batch_id": str(batch.id),
        "status": batch.status,
        "execution_enabled": False,
        "total_count": batch.total_count,
        "finished_count": batch.finished_count,
        "items": [{
            "id": str(item.id),
            "borrower_id": str(item.borrower_id),
            "employee_number": item.employee_number,
            "status": item.status,
            "error_code": item.error_code,
            "assessment_record_id": str(item.assessment_record_id) if item.assessment_record_id else None,
        } for item in items],
    }
