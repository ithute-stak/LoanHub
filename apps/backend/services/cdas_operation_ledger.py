from __future__ import annotations

import hashlib
import json
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import UUID

import httpx
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from database.models.cdas_official import CdasProviderOperation
from integrations.cdas import CdasClient, CdasError


UNRESOLVED_OPERATION_STATES = {
    "prepared",
    "submitting",
    "acknowledged",
    "unknown_provider_state",
    "requires_reconciliation",
}
_RECONCILABLE_STATES = {
    "acknowledged",
    "unknown_provider_state",
    "requires_reconciliation",
}
_LIFECYCLE_STATUS_BY_REQUEST = {1: 1, 3: 3, 4: 4, 6: 6, 10: 10}


class CdasDuplicateOperationError(RuntimeError):
    def __init__(self, operation: CdasProviderOperation) -> None:
        self.operation = operation
        super().__init__(
            f"An unresolved matching CDAS operation already exists ({operation.id}, {operation.state})"
        )


class CdasTrackedProviderError(RuntimeError):
    def __init__(self, provider_error: CdasError, operation: CdasProviderOperation) -> None:
        self.provider_error = provider_error
        self.operation = operation
        super().__init__(provider_error.message)


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


def mark_operation_requires_reconciliation(
    db: Session,
    operation: CdasProviderOperation,
    *,
    message: str,
    reconciliation_snapshot: Any = None,
) -> None:
    operation.state = "requires_reconciliation"
    operation.error_message = message
    operation.requires_reconciliation = True
    if reconciliation_snapshot is not None:
        operation.response_snapshot = {
            "mutation": operation.response_snapshot or {},
            "reconciliation": reconciliation_snapshot,
        }
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


def _provider_error_snapshot(error: CdasError) -> dict[str, Any]:
    details = error.details
    if isinstance(details, dict):
        return details
    if details is None:
        return {}
    return {"raw": details}


def is_ambiguous_write_error(error: CdasError) -> bool:
    """True when the HTTP exchange may have reached CDAS without a response.

    We deliberately inspect the preserved exception cause instead of treating all
    provider 5xx responses as ambiguous. A real CDAS HTTP response is known;
    connect/read/write/protocol failures can leave the mutation outcome unknown.
    """

    return isinstance(error.__cause__, httpx.RequestError)


async def execute_provider_operation(
    db: Session,
    *,
    company_id: UUID,
    branch_id: UUID | None,
    actor_user_id: UUID | None,
    environment: str,
    operation_type: str,
    request_snapshot: dict[str, Any],
    provider_call: Callable[[], Awaitable[dict[str, Any]]],
) -> tuple[dict[str, Any], CdasProviderOperation]:
    operation = begin_provider_operation(
        db,
        company_id=company_id,
        branch_id=branch_id,
        actor_user_id=actor_user_id,
        environment=environment,
        operation_type=operation_type,
        request_snapshot=request_snapshot,
    )
    mark_operation_submitting(db, operation)

    try:
        result = await provider_call()
    except CdasError as error:
        if is_ambiguous_write_error(error):
            mark_operation_unknown(db, operation, error_message=error.message)
        else:
            mark_operation_rejected(
                db,
                operation,
                provider_status_code=error.status_code,
                error_message=error.message,
                response_snapshot=_provider_error_snapshot(error),
            )
        raise CdasTrackedProviderError(error, operation) from error

    mark_operation_acknowledged(
        db,
        operation,
        response_snapshot=result,
        provider_status_code=200,
    )
    return result, operation


def _first_value(source: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = source.get(key)
        if value not in (None, ""):
            return value
    return None


def _normalized_text(value: Any) -> str:
    return str(value or "").strip().casefold()


def _same_money(left: Any, right: Any) -> bool:
    if left in (None, ""):
        return True
    if right in (None, ""):
        return False
    try:
        return Decimal(str(left)) == Decimal(str(right))
    except (InvalidOperation, TypeError, ValueError):
        return False


def _operation_target_deduction_id(operation: CdasProviderOperation) -> int | None:
    response = operation.response_snapshot if isinstance(operation.response_snapshot, dict) else {}
    request = operation.request_snapshot if isinstance(operation.request_snapshot, dict) else {}
    candidate = _first_value(response, "DeductionID", "deductionId", "deduction_id")
    if candidate in (None, "", 0, "0"):
        candidate = _first_value(request, "DeductionID", "deductionId", "deduction_id")
    try:
        return int(candidate) if candidate not in (None, "", 0, "0") else None
    except (TypeError, ValueError):
        return None


def _deduction_matches(operation: CdasProviderOperation, record: dict[str, Any]) -> bool:
    request = operation.request_snapshot if isinstance(operation.request_snapshot, dict) else {}
    target_id = _operation_target_deduction_id(operation)
    record_id = _first_value(record, "DeductionID", "deductionId", "deduction_id")
    if target_id is not None and record_id not in (None, ""):
        try:
            return int(record_id) == target_id
        except (TypeError, ValueError):
            return False

    reference = _normalized_text(_first_value(request, "ReferenceNo", "referenceNo", "reference_no"))
    record_reference = _normalized_text(_first_value(record, "ReferenceNo", "referenceNo", "reference_no"))
    if reference:
        return bool(record_reference and reference == record_reference)

    item_code = _normalized_text(_first_value(request, "ItemCode", "itemCode", "item_code"))
    record_item = _normalized_text(_first_value(record, "ItemCode", "itemCode", "item_code"))
    return bool(item_code and record_item and item_code == record_item)


def _modified_values_match(operation: CdasProviderOperation, record: dict[str, Any]) -> bool:
    request = operation.request_snapshot if isinstance(operation.request_snapshot, dict) else {}
    if not _deduction_matches(operation, record):
        return False
    if not _same_money(request.get("DeductionAmount"), record.get("DeductionAmount")):
        return False
    if not _same_money(request.get("PrincipalAmount"), record.get("PrincipalAmount")):
        return False
    requested_installments = request.get("TotalInstallment")
    returned_installments = record.get("TotalInstallment")
    if requested_installments not in (None, "") and returned_installments not in (None, ""):
        try:
            if int(requested_installments) != int(returned_installments):
                return False
        except (TypeError, ValueError):
            return False
    return True


async def reconcile_provider_operation(
    db: Session,
    *,
    operation: CdasProviderOperation,
    client: CdasClient,
) -> tuple[bool, CdasProviderOperation]:
    """Verify a mutation by reading CDAS state; this function never writes to CDAS."""

    if operation.state == "confirmed":
        return True, operation
    if operation.state not in _RECONCILABLE_STATES:
        raise ValueError(f"CDAS operation state {operation.state!r} is not reconcilable")
    if not operation.employee_no:
        mark_operation_requires_reconciliation(
            db,
            operation,
            message="Operation has no employee number for provider reconciliation",
        )
        return False, operation

    request = operation.request_snapshot if isinstance(operation.request_snapshot, dict) else {}
    mutation_snapshot = operation.response_snapshot if isinstance(operation.response_snapshot, dict) else {}

    try:
        if operation.operation_type == "deduction.modify_active":
            record = await client.get_active_and_approved_deduction(operation.employee_no)
            matched = _modified_values_match(operation, record)
            reconciliation_snapshot: Any = record
        else:
            if operation.operation_type == "deduction.settle":
                expected_status = 7
            elif operation.operation_type.startswith("deduction.lifecycle."):
                try:
                    request_type = int(request.get("RequestType"))
                except (TypeError, ValueError):
                    request_type = -1
                expected_status = _LIFECYCLE_STATUS_BY_REQUEST.get(request_type)
                if expected_status is None:
                    raise ValueError(f"Lifecycle request type {request_type!r} has no reconciliation mapping")
            else:
                raise ValueError(f"Unsupported CDAS operation type {operation.operation_type!r}")

            records = await client.view_own_deductions(operation.employee_no, expected_status)
            record = next((item for item in records if _deduction_matches(operation, item)), None)
            matched = record is not None
            reconciliation_snapshot = record if record is not None else records
    except CdasError as exc:
        mark_operation_requires_reconciliation(
            db,
            operation,
            message=f"CDAS reconciliation read failed: {exc.message}",
        )
        raise

    if matched:
        mark_operation_confirmed(
            db,
            operation,
            response_snapshot={
                "mutation": mutation_snapshot,
                "reconciliation": reconciliation_snapshot,
            },
        )
        return True, operation

    mark_operation_requires_reconciliation(
        db,
        operation,
        message="CDAS read-back did not yet confirm the requested provider state",
        reconciliation_snapshot=reconciliation_snapshot,
    )
    return False, operation


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
