from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from database.models.cdas_official import CdasProviderOperation


UNRESOLVED_OPERATION_STATES = {
    "prepared",
    "submitting",
    "acknowledged",
    "unknown_provider_state",
    "requires_reconciliation",
}


class CdasDuplicateOperationError(RuntimeError):
    def __init__(self, operation: CdasProviderOperation) -> None:
        self.operation = operation
        super().__init__(
            f"An unresolved matching CDAS operation already exists ({operation.id}, {operation.state})"
        )


def _utcnow_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def operation_fingerprint(
    *,
    company_id: UUID,
    environment: str,
    operation_type: str,
    request_snapshot: dict[str, Any],
) -> str:
    canonical = json.dumps(
        {
            "company_id": str(company_id),
            "environment": environment.strip().lower(),
            "operation_type": operation_type.strip().lower(),
            "request": request_snapshot,
        },
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def begin_provider_operation(
    db: Session,
    *,
    company_id: UUID,
    branch_id: UUID | None,
    actor_user_id: UUID | None,
    environment: str,
    operation_type: str,
    request_snapshot: dict[str, Any],
) -> CdasProviderOperation:
    environment = environment.strip().lower()
    fingerprint = operation_fingerprint(
        company_id=company_id,
        environment=environment,
        operation_type=operation_type,
        request_snapshot=request_snapshot,
    )
    operation = CdasProviderOperation(
        company_id=company_id,
        branch_id=branch_id,
        actor_user_id=actor_user_id,
        environment=environment,
        operation_type=operation_type,
        state="prepared",
        employee_no=str(request_snapshot.get("EmployeeNo") or "").strip() or None,
        deduction_id=(
            int(request_snapshot["DeductionID"])
            if request_snapshot.get("DeductionID") not in (None, "")
            else None
        ),
        reference_no=str(request_snapshot.get("ReferenceNo") or "").strip() or None,
        fingerprint=fingerprint,
        request_snapshot=request_snapshot,
        response_snapshot={},
        requires_reconciliation=False,
    )
    db.add(operation)
    try:
        db.commit()
        db.refresh(operation)
        return operation
    except IntegrityError as exc:
        db.rollback()
        existing = (
            db.query(CdasProviderOperation)
            .filter(
                CdasProviderOperation.company_id == company_id,
                CdasProviderOperation.environment == environment,
                CdasProviderOperation.fingerprint == fingerprint,
                CdasProviderOperation.state.in_(UNRESOLVED_OPERATION_STATES),
            )
            .order_by(CdasProviderOperation.created_at.desc())
            .first()
        )
        if existing is not None:
            raise CdasDuplicateOperationError(existing) from exc
        raise


def mark_operation_submitting(db: Session, operation: CdasProviderOperation) -> None:
    operation.state = "submitting"
    operation.submitted_at = _utcnow_naive()
    db.commit()
    db.refresh(operation)


def mark_operation_acknowledged(
    db: Session,
    operation: CdasProviderOperation,
    *,
    response_snapshot: dict[str, Any],
    provider_status_code: int | None = 200,
) -> None:
    operation.state = "acknowledged"
    operation.response_snapshot = response_snapshot
    operation.provider_status_code = provider_status_code
    operation.error_message = None
    operation.requires_reconciliation = True
    db.commit()
    db.refresh(operation)


def mark_operation_rejected(
    db: Session,
    operation: CdasProviderOperation,
    *,
    provider_status_code: int | None,
    error_message: str,
    response_snapshot: dict[str, Any] | None = None,
) -> None:
    operation.state = "rejected"
    operation.provider_status_code = provider_status_code
    operation.error_message = error_message
    operation.response_snapshot = response_snapshot or {}
    operation.requires_reconciliation = False
    operation.completed_at = _utcnow_naive()
    db.commit()
    db.refresh(operation)


def mark_operation_unknown(
    db: Session,
    operation: CdasProviderOperation,
    *,
    error_message: str,
) -> None:
    operation.state = "unknown_provider_state"
    operation.error_message = error_message
    operation.requires_reconciliation = True
    db.commit()
    db.refresh(operation)


def mark_operation_confirmed(
    db: Session,
    operation: CdasProviderOperation,
    *,
    response_snapshot: dict[str, Any] | None = None,
) -> None:
    operation.state = "confirmed"
    if response_snapshot is not None:
        operation.response_snapshot = response_snapshot
    operation.error_message = None
    operation.requires_reconciliation = False
    now = _utcnow_naive()
    operation.reconciled_at = now
    operation.completed_at = now
    db.commit()
    db.refresh(operation)


def operation_summary(operation: CdasProviderOperation) -> dict[str, Any]:
    return {
        "id": str(operation.id),
        "company_id": str(operation.company_id),
        "branch_id": str(operation.branch_id) if operation.branch_id else None,
        "actor_user_id": str(operation.actor_user_id) if operation.actor_user_id else None,
        "environment": operation.environment,
        "operation_type": operation.operation_type,
        "state": operation.state,
        "employee_no": operation.employee_no,
        "deduction_id": operation.deduction_id,
        "reference_no": operation.reference_no,
        "fingerprint": operation.fingerprint,
        "request_snapshot": operation.request_snapshot or {},
        "response_snapshot": operation.response_snapshot or {},
        "provider_status_code": operation.provider_status_code,
        "error_message": operation.error_message,
        "requires_reconciliation": bool(operation.requires_reconciliation),
        "submitted_at": operation.submitted_at.isoformat() if operation.submitted_at else None,
        "completed_at": operation.completed_at.isoformat() if operation.completed_at else None,
        "reconciled_at": operation.reconciled_at.isoformat() if operation.reconciled_at else None,
        "created_at": operation.created_at.isoformat() if operation.created_at else None,
        "updated_at": operation.updated_at.isoformat() if operation.updated_at else None,
    }
