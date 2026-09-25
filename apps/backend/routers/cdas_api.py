from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from core.access_control import (
    COMPANY_MANAGEMENT_ROLES,
    LENDING_ROLES,
    TenantContext,
    get_tenant_context,
    require_tenant_roles,
)
from database.models.audit_log import AuditLog
from database.models.cdas_official import CdasProviderOperation
from database.session import get_db
from integrations.cdas import CdasClient, CdasError
from integrations.cdas_contracts import (
    CdasLifecyclePayload,
    CdasModifyActivePayload,
    CdasSettlementPayload,
)
from services.cdas_config_service import (
    configuration_summary,
    get_company_cdas_client,
    get_configuration,
    test_company_configuration,
    update_configuration,
)
from services.cdas_operation_ledger import (
    CdasDuplicateOperationError,
    CdasTrackedProviderError,
    execute_provider_operation,
    operation_summary,
    reconcile_provider_operation,
)
from services.cdas_request_budget import get_cdas_request_budget_status

router = APIRouter(prefix="/cdas", tags=["CDAS"])


class CdasConfigurationUpdateRequest(BaseModel):
    environment: Literal["test", "live"] = "test"
    enabled: bool = False
    base_url: str = Field(min_length=8, max_length=500)
    username: str = Field(min_length=1, max_length=200)
    password: str | None = Field(default=None, max_length=500)
    clear_password: bool = False
    timeout_seconds: float = Field(default=20.0, ge=1, le=120)


class CdasEmployeeLookupRequest(BaseModel):
    employee_no: str = Field(min_length=1, max_length=100)


class CdasOwnDeductionLookupRequest(CdasEmployeeLookupRequest):
    deduction_status: int = Field(ge=1, le=10)


class CdasDeductionLifecycleRequest(CdasLifecyclePayload):
    confirmed: bool = False


class CdasModifyActiveDeductionRequest(CdasModifyActivePayload):
    confirmed: bool = False


class CdasSettleDeductionRequest(CdasSettlementPayload):
    confirmed: bool = False


class CdasDocumentRequest(BaseModel):
    year: int = Field(ge=1, le=9999)
    month: int = Field(ge=1, le=12)
    document_type: int = Field(ge=1, le=2)


def _require_company_manager(context: TenantContext) -> None:
    if context.is_platform_admin or not context.company_id or not context.staff:
        raise HTTPException(status_code=403, detail="A company-scoped membership is required")
    require_tenant_roles(context, COMPANY_MANAGEMENT_ROLES)


def _require_lending_user(context: TenantContext) -> None:
    if context.is_platform_admin or not context.company_id or not context.staff:
        raise HTTPException(status_code=403, detail="A company-scoped membership is required")
    require_tenant_roles(context, LENDING_ROLES)


def _require_confirmed(confirmed: bool) -> None:
    if not confirmed:
        raise HTTPException(
            status_code=409,
            detail="Explicit confirmation is required for this CDAS state-changing action",
        )


def _cdas_http_error(exc: CdasError, *, operation: CdasProviderOperation | None = None) -> HTTPException:
    status = exc.status_code if 400 <= exc.status_code <= 599 else 502
    detail: dict[str, Any] = {
        "provider": "CDAS",
        "code": exc.status_code,
        "message": exc.message,
    }
    if operation is not None:
        detail["operation"] = operation_summary(operation)
    return HTTPException(status_code=status, detail=detail)


def _duplicate_operation_error(exc: CdasDuplicateOperationError) -> HTTPException:
    return HTTPException(
        status_code=409,
        detail={
            "provider": "CDAS",
            "code": "CDAS_DUPLICATE_UNRESOLVED_OPERATION",
            "message": "An identical CDAS mutation is still unresolved. Reconcile it before submitting again.",
            "operation": operation_summary(exc.operation),
        },
    )


def _company_cdas_environment(db: Session, company_id: UUID) -> str:
    row = get_configuration(db, company_id)
    return str(row.environment or "test").strip().lower() if row else "test"


def _record_cdas_mutation_audit(
    db: Session,
    context: TenantContext,
    *,
    action: str,
    request_data: dict[str, Any],
    status: str,
    provider_data: dict[str, Any],
) -> None:
    """Best-effort audit record; audit persistence must not repeat a provider mutation."""

    try:
        db.add(
            AuditLog(
                user_id=context.user.id,
                company_id=context.company_id,
                branch_id=context.branch_id,
                action=action,
                table_name="cdas",
                entity_type="external_payroll_deduction",
                description="User-initiated CDAS deduction operation",
                actor_role=getattr(context.role, "value", str(context.role)),
                severity="info" if status == "success" else "warning",
                status=status,
                event_data={
                    "request": request_data,
                    "provider": provider_data,
                },
            )
        )
        db.commit()
    except Exception:
        db.rollback()


async def _execute_tracked_mutation(
    *,
    db: Session,
    context: TenantContext,
    client: CdasClient,
    operation_type: str,
    audit_action: str,
    provider_request: dict[str, Any],
    ledger_request: dict[str, Any],
    provider_call: Callable[[], Awaitable[dict[str, Any]]],
) -> dict[str, Any]:
    assert context.company_id is not None
    environment = _company_cdas_environment(db, context.company_id)
    try:
        result, operation = await execute_provider_operation(
            db,
            company_id=context.company_id,
            branch_id=context.branch_id,
            actor_user_id=context.user.id,
            environment=environment,
            operation_type=operation_type,
            request_snapshot=ledger_request,
            provider_call=provider_call,
        )
    except CdasDuplicateOperationError as exc:
        raise _duplicate_operation_error(exc) from exc
    except CdasTrackedProviderError as exc:
        _record_cdas_mutation_audit(
            db,
            context,
            action=audit_action,
            request_data=ledger_request,
            status="failed",
            provider_data={
                "code": exc.provider_error.status_code,
                "message": exc.provider_error.message,
                "operation": operation_summary(exc.operation),
            },
        )
        raise _cdas_http_error(exc.provider_error, operation=exc.operation) from exc

    reconciled = False
    try:
        reconciled, operation = await reconcile_provider_operation(
            db,
            operation=operation,
            client=client,
        )
    except CdasError:
        # The provider already acknowledged the mutation. A failed read-back must
        # never turn that into a retryable write failure; the ledger remains in a
        # reconciliation-required state for a later explicit read-only check.
        db.refresh(operation)

    summary = operation_summary(operation)
    _record_cdas_mutation_audit(
        db,
        context,
        action=audit_action,
        request_data=ledger_request,
        status="success" if reconciled else "warning",
        provider_data={
            "response": result,
            "operation": summary,
            "reconciled": reconciled,
        },
    )
    return {
        "ok": True,
        "deduction": result,
        "reconciled": reconciled,
        "operation": summary,
    }


@router.get("/configuration")
def get_cdas_configuration(
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
):
    _require_company_manager(context)
    assert context.company_id is not None
    return configuration_summary(get_configuration(db, context.company_id))


@router.put("/configuration")
def put_cdas_configuration(
    payload: CdasConfigurationUpdateRequest,
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
):
    _require_company_manager(context)
    assert context.company_id is not None
    try:
        row = update_configuration(
            db,
            company_id=context.company_id,
            configured_by_user_id=context.user.id,
            environment=payload.environment,
            enabled=payload.enabled,
            base_url=payload.base_url,
            username=payload.username,
            password=payload.password,
            clear_password=payload.clear_password,
            timeout_seconds=payload.timeout_seconds,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return configuration_summary(row)


@router.post("/configuration/test")
async def test_cdas_configuration(
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
):
    _require_company_manager(context)
    assert context.company_id is not None
    try:
        configuration = await test_company_configuration(db, company_id=context.company_id)
    except CdasError as exc:
        raise _cdas_http_error(exc) from exc
    return {"ok": True, "configuration": configuration}


@router.get("/request-budget")
def get_cdas_request_budget(
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
):
    """Return LoanHub's local CDAS quota counter without contacting CDAS."""
    _require_lending_user(context)
    assert context.company_id is not None
    row = get_configuration(db, context.company_id)
    environment = str(row.environment or "test").strip().lower() if row else "test"
    return get_cdas_request_budget_status(db, company_id=context.company_id, environment=environment)


@router.get("/operations")
def list_cdas_operations(
    state: str | None = Query(default=None, max_length=40),
    limit: int = Query(default=50, ge=1, le=200),
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
):
    """Return the company's local CDAS mutation ledger without contacting CDAS."""
    _require_company_manager(context)
    assert context.company_id is not None
    query = db.query(CdasProviderOperation).filter(CdasProviderOperation.company_id == context.company_id)
    if state:
        query = query.filter(CdasProviderOperation.state == state.strip().lower())
    rows = query.order_by(CdasProviderOperation.created_at.desc()).limit(limit).all()
    return {"items": [operation_summary(row) for row in rows], "count": len(rows)}


@router.get("/operations/{operation_id}")
def get_cdas_operation(
    operation_id: UUID,
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
):
    _require_company_manager(context)
    assert context.company_id is not None
    row = db.query(CdasProviderOperation).filter(
        CdasProviderOperation.id == operation_id,
        CdasProviderOperation.company_id == context.company_id,
    ).one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="CDAS operation not found")
    return operation_summary(row)


@router.post("/operations/{operation_id}/reconcile")
async def reconcile_cdas_operation(
    operation_id: UUID,
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
):
    """Read CDAS to reconcile one mutation; this endpoint never replays a write."""
    _require_company_manager(context)
    assert context.company_id is not None
    operation = db.query(CdasProviderOperation).filter(
        CdasProviderOperation.id == operation_id,
        CdasProviderOperation.company_id == context.company_id,
    ).one_or_none()
    if operation is None:
        raise HTTPException(status_code=404, detail="CDAS operation not found")

    current_environment = _company_cdas_environment(db, context.company_id)
    if operation.environment != current_environment:
        raise HTTPException(
            status_code=409,
            detail="This CDAS operation belongs to a different provider environment",
        )

    try:
        client = get_company_cdas_client(db, context.company_id)
        matched, operation = await reconcile_provider_operation(db, operation=operation, client=client)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except CdasError as exc:
        db.refresh(operation)
        raise _cdas_http_error(exc, operation=operation) from exc

    return {"ok": True, "reconciled": matched, "operation": operation_summary(operation)}


@router.post("/employees/verify")
async def verify_cdas_employee(
    payload: CdasEmployeeLookupRequest,
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
):
    _require_lending_user(context)
    assert context.company_id is not None
    try:
        client = get_company_cdas_client(db, context.company_id)
        employee = await client.get_employee_details(payload.employee_no)
    except CdasError as exc:
        raise _cdas_http_error(exc) from exc
    return {"ok": True, "employee": employee}


@router.post("/employees/affordability")
async def check_cdas_affordability(
    payload: CdasEmployeeLookupRequest,
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
):
    _require_lending_user(context)
    assert context.company_id is not None
    try:
        client = get_company_cdas_client(db, context.company_id)
        affordability = await client.check_affordability(payload.employee_no)
    except CdasError as exc:
        raise _cdas_http_error(exc) from exc
    return {"ok": True, "affordability": affordability}


@router.post("/deductions/all")
async def view_all_cdas_deductions(
    payload: CdasEmployeeLookupRequest,
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
):
    _require_lending_user(context)
    assert context.company_id is not None
    try:
        client = get_company_cdas_client(db, context.company_id)
        deductions = await client.view_all_deductions(payload.employee_no)
    except CdasError as exc:
        raise _cdas_http_error(exc) from exc
    return {"ok": True, "deductions": deductions}


@router.post("/deductions/own")
async def view_own_cdas_deductions(
    payload: CdasOwnDeductionLookupRequest,
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
):
    _require_lending_user(context)
    assert context.company_id is not None
    try:
        client = get_company_cdas_client(db, context.company_id)
        deductions = await client.view_own_deductions(payload.employee_no, payload.deduction_status)
    except CdasError as exc:
        raise _cdas_http_error(exc) from exc
    return {"ok": True, "deductions": deductions}


@router.post("/deductions/active-approved")
async def get_active_approved_cdas_deduction(
    payload: CdasEmployeeLookupRequest,
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
):
    _require_lending_user(context)
    assert context.company_id is not None
    try:
        client = get_company_cdas_client(db, context.company_id)
        deduction = await client.get_active_and_approved_deduction(payload.employee_no)
    except CdasError as exc:
        raise _cdas_http_error(exc) from exc
    return {"ok": True, "deduction": deduction}


@router.post("/deductions/lifecycle")
async def change_cdas_deduction_lifecycle(
    payload: CdasDeductionLifecycleRequest,
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
):
    _require_company_manager(context)
    _require_confirmed(payload.confirmed)
    assert context.company_id is not None
    client = get_company_cdas_client(db, context.company_id)
    provider_request = payload.provider_payload()
    ledger_request = payload.ledger_payload()
    return await _execute_tracked_mutation(
        db=db,
        context=context,
        client=client,
        operation_type=f"deduction.lifecycle.{payload.request_type}",
        audit_action="cdas.deduction.lifecycle",
        provider_request=provider_request,
        ledger_request=ledger_request,
        provider_call=lambda: client.add_update_deduction(provider_request),
    )


@router.post("/deductions/modify-active")
async def modify_active_cdas_deduction(
    payload: CdasModifyActiveDeductionRequest,
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
):
    _require_company_manager(context)
    _require_confirmed(payload.confirmed)
    assert context.company_id is not None
    client = get_company_cdas_client(db, context.company_id)
    provider_request = payload.provider_payload()
    ledger_request = payload.ledger_payload()
    return await _execute_tracked_mutation(
        db=db,
        context=context,
        client=client,
        operation_type="deduction.modify_active",
        audit_action="cdas.deduction.modify_active",
        provider_request=provider_request,
        ledger_request=ledger_request,
        provider_call=lambda: client.modify_active_deduction(provider_request),
    )


@router.post("/deductions/settle")
async def settle_cdas_deduction(
    payload: CdasSettleDeductionRequest,
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
):
    _require_company_manager(context)
    _require_confirmed(payload.confirmed)
    assert context.company_id is not None
    client = get_company_cdas_client(db, context.company_id)
    provider_request = payload.provider_payload()
    ledger_request = payload.ledger_payload()
    return await _execute_tracked_mutation(
        db=db,
        context=context,
        client=client,
        operation_type="deduction.settle",
        audit_action="cdas.deduction.settle",
        provider_request=provider_request,
        ledger_request=ledger_request,
        provider_call=lambda: client.settle_deduction(provider_request),
    )


@router.post("/documents")
async def get_cdas_document(
    payload: CdasDocumentRequest,
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
):
    _require_company_manager(context)
    assert context.company_id is not None
    try:
        client = get_company_cdas_client(db, context.company_id)
        document = await client.get_document(
            year=payload.year,
            month=payload.month,
            document_type=payload.document_type,
        )
    except CdasError as exc:
        raise _cdas_http_error(exc) from exc
    return {"ok": True, "document": document}
