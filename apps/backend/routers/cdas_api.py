from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
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
from database.session import get_db
from integrations.cdas import CdasError
from services.cdas_config_service import (
    configuration_summary,
    get_company_cdas_client,
    get_configuration,
    test_company_configuration,
    update_configuration,
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


class CdasDeductionLifecycleRequest(BaseModel):
    request_type: Literal[1, 3, 4, 6, 10]
    deduction_id: int = Field(ge=0)
    employee_no: str = Field(min_length=1, max_length=100)
    loan_policy: Literal[1, 2]
    item_code: str = Field(min_length=1, max_length=100)
    deduction_amount: float = Field(ge=0)
    total_installment: int = Field(ge=0)
    principal_amount: float = Field(ge=0)
    effective_month: str = Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")
    reference_no: str = Field(min_length=1, max_length=200)
    confirmed: bool = False


class CdasModifyActiveDeductionRequest(BaseModel):
    employee_no: str = Field(min_length=1, max_length=100)
    item_code: str = Field(min_length=1, max_length=100)
    total_installment: int = Field(gt=0)
    deduction_amount: float = Field(gt=0)
    principal_amount: float = Field(gt=0)
    deduction_id: int = Field(ge=0)
    effective_date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    confirmed: bool = False


class CdasSettleDeductionRequest(BaseModel):
    item_code: str = Field(min_length=1, max_length=100)
    deduction_id: int = Field(ge=0)
    effective_date: str = Field(min_length=10, max_length=50)
    employee_no: str = Field(min_length=1, max_length=100)
    settlement_reason: int = Field(ge=1, le=4)
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


def _cdas_http_error(exc: CdasError) -> HTTPException:
    status = exc.status_code if 400 <= exc.status_code <= 599 else 502
    return HTTPException(
        status_code=status,
        detail={
            "provider": "CDAS",
            "code": exc.status_code,
            "message": exc.message,
        },
    )


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
        configuration = await test_company_configuration(
            db,
            company_id=context.company_id,
        )
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
    return get_cdas_request_budget_status(
        db,
        company_id=context.company_id,
        environment=environment,
    )


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
        deductions = await client.view_own_deductions(
            payload.employee_no,
            payload.deduction_status,
        )
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

    request_data = {
        "RequestType": payload.request_type,
        "DeductionID": payload.deduction_id,
        "EmployeeNo": payload.employee_no.strip(),
        "LoanPolicy": payload.loan_policy,
        "ItemCode": payload.item_code.strip(),
        "DeductionAmount": payload.deduction_amount,
        "TotalInstallment": payload.total_installment,
        "PrincipalAmount": payload.principal_amount,
        "EffectiveMonth": payload.effective_month,
        "ReferenceNo": payload.reference_no.strip(),
    }
    try:
        client = get_company_cdas_client(db, context.company_id)
        result = await client.add_update_deduction(request_data)
    except CdasError as exc:
        _record_cdas_mutation_audit(
            db,
            context,
            action="cdas.deduction.lifecycle",
            request_data=request_data,
            status="failed",
            provider_data={"code": exc.status_code, "message": exc.message},
        )
        raise _cdas_http_error(exc) from exc

    _record_cdas_mutation_audit(
        db,
        context,
        action="cdas.deduction.lifecycle",
        request_data=request_data,
        status="success",
        provider_data=result,
    )
    return {"ok": True, "deduction": result}


@router.post("/deductions/modify-active")
async def modify_active_cdas_deduction(
    payload: CdasModifyActiveDeductionRequest,
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
):
    _require_company_manager(context)
    _require_confirmed(payload.confirmed)
    assert context.company_id is not None

    request_data = {
        "EmployeeNo": payload.employee_no.strip(),
        "ItemCode": payload.item_code.strip(),
        "TotalInstallment": payload.total_installment,
        "DeductionAmount": payload.deduction_amount,
        "PrincipalAmount": payload.principal_amount,
        "DeductionID": payload.deduction_id,
        "EffectiveDate": payload.effective_date,
    }
    try:
        client = get_company_cdas_client(db, context.company_id)
        result = await client.modify_active_deduction(request_data)
    except CdasError as exc:
        _record_cdas_mutation_audit(
            db,
            context,
            action="cdas.deduction.modify_active",
            request_data=request_data,
            status="failed",
            provider_data={"code": exc.status_code, "message": exc.message},
        )
        raise _cdas_http_error(exc) from exc

    _record_cdas_mutation_audit(
        db,
        context,
        action="cdas.deduction.modify_active",
        request_data=request_data,
        status="success",
        provider_data=result,
    )
    return {"ok": True, "deduction": result}


@router.post("/deductions/settle")
async def settle_cdas_deduction(
    payload: CdasSettleDeductionRequest,
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
):
    _require_company_manager(context)
    _require_confirmed(payload.confirmed)
    assert context.company_id is not None

    request_data = {
        "ItemCode": payload.item_code.strip(),
        "DeductionID": payload.deduction_id,
        "EffectiveDate": payload.effective_date.strip(),
        "EmployeeNo": payload.employee_no.strip(),
        "SettlementReason": payload.settlement_reason,
    }
    try:
        client = get_company_cdas_client(db, context.company_id)
        result = await client.settle_deduction(request_data)
    except CdasError as exc:
        _record_cdas_mutation_audit(
            db,
            context,
            action="cdas.deduction.settle",
            request_data=request_data,
            status="failed",
            provider_data={"code": exc.status_code, "message": exc.message},
        )
        raise _cdas_http_error(exc) from exc

    _record_cdas_mutation_audit(
        db,
        context,
        action="cdas.deduction.settle",
        request_data=request_data,
        status="success",
        provider_data=result,
    )
    return {"ok": True, "deduction": result}


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
