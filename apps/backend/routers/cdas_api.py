from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from core.access_control import (
    COLLECTIONS_ROLES,
    COMPANY_MANAGEMENT_ROLES,
    FINANCE_ROLES,
    LENDING_ROLES,
    TenantContext,
    get_tenant_context,
    require_tenant_roles,
)
from database.models.enums import UserRole
from database.session import get_db
from integrations.cdas import CdasClient, CdasError
from services.cdas_analysis_history import (
    save_or_get_analysis_record,
    serialize_analysis_record,
)
from services.cdas_config_service import (
    configuration_summary,
    get_company_cdas_client,
    get_configuration,
    test_company_configuration,
    update_configuration,
)
from services.cdas_official_snapshot import normalize_official_cdas_snapshot


router = APIRouter(prefix="/cdas", tags=["CDAS Official API"])

# CDAS contains employee identity, affordability and payroll-deduction data.
# Company membership by itself is not enough to query it. Keep operational
# access to lending/finance/collections and explicit oversight roles.
CDAS_READ_ROLES = (
    set(LENDING_ROLES)
    | set(FINANCE_ROLES)
    | set(COLLECTIONS_ROLES)
    | {UserRole.COMPLIANCE_OFFICER, UserRole.AUDITOR, UserRole.RISK_MANAGER}
)
CDAS_DOCUMENT_ROLES = (
    set(FINANCE_ROLES)
    | set(COLLECTIONS_ROLES)
    | {UserRole.COMPLIANCE_OFFICER, UserRole.AUDITOR}
)

# These legacy role groups are intentionally retained as documentation of who
# may perform writes through the loan-linked lifecycle router. Raw provider
# write routes below are disabled so they cannot bypass the LoanHub loan link,
# lifecycle ordering, reconciliation rules or append-only audit ledger.
CDAS_DEDUCTION_WRITE_ROLES = set(LENDING_ROLES)
CDAS_SETTLEMENT_ROLES = set(LENDING_ROLES) | set(FINANCE_ROLES) | set(COLLECTIONS_ROLES)
RAW_WRITE_DISABLED_MESSAGE = (
    "Direct CDAS provider writes are disabled. Use the loan-linked CDAS lifecycle endpoints so the operation is tied to a LoanHub loan, validated, reconciled and audited."
)


class CdasConfigurationUpdateRequest(BaseModel):
    environment: Literal["test", "live"] = "test"
    enabled: bool = False
    base_url: str = Field(min_length=8, max_length=500)
    username: str = Field(min_length=1, max_length=200)
    password: str | None = Field(default=None, max_length=500)
    clear_password: bool = False
    timeout_seconds: float = Field(default=20.0, ge=1, le=120)


class CdasRefreshRequest(BaseModel):
    employee_no: str = Field(min_length=1, max_length=100)
    own_deduction_status: int | None = Field(default=None, ge=1, le=10)


class CdasDeductionActionRequest(BaseModel):
    # CDAS v1.5 does not define RequestType 2. Preserve the documented duplicate
    # values for 6 and 8 instead of inventing a meaning for the missing code.
    request_type: Literal[1, 3, 4, 5, 6, 7, 8, 9, 10]
    deduction_id: int = Field(default=0, ge=0)
    employee_no: str = Field(min_length=1, max_length=100)
    loan_policy: int = Field(default=0, ge=0)
    item_code: str = Field(min_length=1, max_length=100)
    deduction_amount: float = Field(ge=0)
    total_installment: int = Field(default=0, ge=0)
    principal_amount: float = Field(ge=0)
    effective_month: str = Field(min_length=7, max_length=32)
    reference_no: str = Field(min_length=1, max_length=200)

    def to_cdas_payload(self) -> dict[str, Any]:
        return {
            "RequestType": self.request_type,
            "DeductionID": self.deduction_id,
            "EmployeeNo": self.employee_no,
            "LoanPolicy": self.loan_policy,
            "ItemCode": self.item_code,
            "DeductionAmount": self.deduction_amount,
            "TotalInstallment": self.total_installment,
            "PrincipalAmount": self.principal_amount,
            "EffectiveMonth": self.effective_month,
            "ReferenceNo": self.reference_no,
        }


class CdasModifyActiveDeductionRequest(BaseModel):
    employee_no: str = Field(min_length=1, max_length=100)
    item_code: str = Field(min_length=1, max_length=100)
    total_installment: int = Field(ge=0)
    deduction_amount: float = Field(ge=0)
    principal_amount: float = Field(ge=0)
    deduction_id: int = Field(gt=0)
    effective_date: str = Field(min_length=7, max_length=40)

    def to_cdas_payload(self) -> dict[str, Any]:
        return {
            "EmployeeNo": self.employee_no,
            "ItemCode": self.item_code,
            "TotalInstallment": self.total_installment,
            "DeductionAmount": self.deduction_amount,
            "PrincipalAmount": self.principal_amount,
            "DeductionID": self.deduction_id,
            "EffectiveDate": self.effective_date,
        }


class CdasSettleDeductionRequest(BaseModel):
    item_code: str = Field(min_length=1, max_length=100)
    deduction_id: int = Field(gt=0)
    effective_date: str = Field(min_length=7, max_length=40)
    employee_no: str = Field(min_length=1, max_length=100)
    settlement_reason: int = Field(ge=1, le=4)

    def to_cdas_payload(self) -> dict[str, Any]:
        return {
            "ItemCode": self.item_code,
            "DeductionID": self.deduction_id,
            "EffectiveDate": self.effective_date,
            "EmployeeNo": self.employee_no,
            "SettlementReason": self.settlement_reason,
        }


def _require_company_member(context: TenantContext) -> None:
    if context.is_platform_admin or not context.company_id or not context.staff:
        raise HTTPException(status_code=403, detail="A company-scoped membership is required")


def _require_company_manager(context: TenantContext) -> None:
    _require_company_member(context)
    require_tenant_roles(context, COMPANY_MANAGEMENT_ROLES)


def _require_cdas_reader(context: TenantContext) -> None:
    _require_company_member(context)
    require_tenant_roles(context, CDAS_READ_ROLES)


def _require_deduction_writer(context: TenantContext) -> None:
    _require_company_member(context)
    raise HTTPException(status_code=410, detail=RAW_WRITE_DISABLED_MESSAGE)


def _require_settlement_writer(context: TenantContext) -> None:
    _require_company_member(context)
    raise HTTPException(status_code=410, detail=RAW_WRITE_DISABLED_MESSAGE)


def _company_client(db: Session, context: TenantContext) -> CdasClient:
    _require_cdas_reader(context)
    assert context.company_id is not None
    try:
        return get_company_cdas_client(db, context.company_id)
    except CdasError as exc:
        raise _cdas_http_error(exc) from exc


def _report_preparer(context: TenantContext) -> tuple[str, str]:
    person = getattr(context.user, "person", None)
    prepared_by = (
        str(getattr(person, "full_name", "") or "").strip()
        or str(context.user.email or "").strip()
        or str(context.user.phone or "").strip()
        or "Authorized company user"
    )
    role = getattr(context.role, "value", None) or str(context.role)
    return prepared_by, str(role)


def _cdas_http_error(exc: CdasError) -> HTTPException:
    # Never pass the upstream response wholesale to the client because CDAS may
    # include implementation detail that is inappropriate for LoanHub clients.
    status = exc.status_code if 400 <= exc.status_code <= 599 else 502
    return HTTPException(
        status_code=status,
        detail={"provider": "CDAS", "code": exc.status_code, "message": exc.message},
    )


@router.get("/configuration")
def get_cdas_configuration(
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
):
    """Return this company's sanitized CDAS configuration; never return its password."""
    _require_company_manager(context)
    assert context.company_id is not None
    return configuration_summary(get_configuration(db, context.company_id))


@router.put("/configuration")
def put_cdas_configuration(
    payload: CdasConfigurationUpdateRequest,
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
):
    """Create or update company-owned Test/Live CDAS credentials."""
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
    """Authenticate using the stored company credential without exposing a CDAS token."""
    _require_company_manager(context)
    assert context.company_id is not None
    try:
        configuration = await test_company_configuration(db, company_id=context.company_id)
    except CdasError as exc:
        raise _cdas_http_error(exc) from exc
    return {"ok": True, "configuration": configuration}


@router.get("/employees/{employee_no}")
async def get_cdas_employee(
    employee_no: str,
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
):
    """Read the employee identity using this company's official CDAS account."""
    client = _company_client(db, context)
    try:
        return await client.employee_details(employee_no.strip())
    except CdasError as exc:
        raise _cdas_http_error(exc) from exc


@router.get("/employees/{employee_no}/affordability")
async def get_cdas_affordability(
    employee_no: str,
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
):
    """Read current CDAS affordability. No value is calculated locally."""
    client = _company_client(db, context)
    try:
        amount = await client.affordability(employee_no.strip())
        return {"employee_no": employee_no.strip(), "affordability": amount, "source": "CDAS_API"}
    except CdasError as exc:
        raise _cdas_http_error(exc) from exc


@router.get("/employees/{employee_no}/deductions")
async def get_cdas_deductions(
    employee_no: str,
    own_only: bool = Query(default=False),
    deduction_status: int | None = Query(default=None, ge=1, le=10),
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
):
    """Read all deductions or the connected company's deductions for a status."""
    client = _company_client(db, context)
    employee_no = employee_no.strip()
    try:
        if own_only:
            if deduction_status is None:
                raise HTTPException(
                    status_code=422,
                    detail="deduction_status is required when own_only=true",
                )
            items = await client.own_deductions(employee_no, deduction_status)
        else:
            items = await client.all_deductions(employee_no)
        return {"employee_no": employee_no, "items": items, "total": len(items), "source": "CDAS_API"}
    except CdasError as exc:
        raise _cdas_http_error(exc) from exc


@router.post("/refresh")
async def refresh_cdas_employee_snapshot(
    payload: CdasRefreshRequest,
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
):
    """Refresh one employee from CDAS and archive the material official snapshot.

    This operation is deliberately user-triggered. It does not register, modify,
    approve, settle or book a deduction. An unchanged official snapshot reuses
    its existing Analysis History record instead of creating a timestamp-only
    duplicate.
    """
    client = _company_client(db, context)
    assert context.company_id is not None
    employee_no = payload.employee_no.strip()
    try:
        raw_snapshot = await client.refresh_employee_snapshot(
            employee_no,
            own_deduction_status=payload.own_deduction_status,
        )
    except CdasError as exc:
        raise _cdas_http_error(exc) from exc

    analysis = normalize_official_cdas_snapshot(
        raw_snapshot,
        own_deduction_status=payload.own_deduction_status,
    )
    profile = analysis.get("profile") or {}
    prepared_by, prepared_by_role = _report_preparer(context)
    record, created = save_or_get_analysis_record(
        db,
        company_id=context.company_id,
        analyzed_by_user_id=context.user.id,
        analyzed_by_name=prepared_by,
        analyzed_by_role=prepared_by_role,
        client_name=profile.get("full_name"),
        client_reference=profile.get("employee_no") or employee_no,
        analysis=analysis,
    )
    return {
        "source": "CDAS_API",
        "checked_at": raw_snapshot.get("checked_at"),
        "snapshot": analysis,
        "archive": {
            "created": created,
            "record": serialize_analysis_record(record),
        },
    }


@router.post("/deductions/actions")
async def run_cdas_deduction_action(
    payload: CdasDeductionActionRequest,
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
):
    """Disabled raw provider write; use the loan-linked lifecycle route."""
    _require_deduction_writer(context)
    client = _company_client(db, context)
    try:
        return await client.add_update_deduction(payload.to_cdas_payload())
    except CdasError as exc:
        raise _cdas_http_error(exc) from exc


@router.get("/employees/{employee_no}/active-approved-deductions")
async def get_active_and_approved_cdas_deductions(
    employee_no: str,
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
):
    client = _company_client(db, context)
    try:
        return await client.active_and_approved_deductions(employee_no.strip())
    except CdasError as exc:
        raise _cdas_http_error(exc) from exc


@router.post("/deductions/modify-active")
async def modify_active_cdas_deduction(
    payload: CdasModifyActiveDeductionRequest,
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
):
    """Disabled raw provider write; use the loan-linked lifecycle route."""
    _require_deduction_writer(context)
    client = _company_client(db, context)
    try:
        return await client.modify_active_deduction(payload.to_cdas_payload())
    except CdasError as exc:
        raise _cdas_http_error(exc) from exc


@router.post("/deductions/settle")
async def settle_cdas_deduction(
    payload: CdasSettleDeductionRequest,
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
):
    """Disabled raw provider write; use the loan-linked lifecycle route."""
    _require_settlement_writer(context)
    client = _company_client(db, context)
    try:
        return await client.settle_deduction(payload.to_cdas_payload())
    except CdasError as exc:
        raise _cdas_http_error(exc) from exc


@router.get("/documents")
async def get_cdas_document(
    year: int = Query(ge=2000, le=2200),
    month: int = Query(ge=1, le=12),
    document_type: int = Query(ge=1, le=2),
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
):
    _require_company_member(context)
    require_tenant_roles(context, CDAS_DOCUMENT_ROLES)
    client = _company_client(db, context)
    try:
        return await client.get_document(
            year=year,
            month=month,
            document_type=document_type,
        )
    except CdasError as exc:
        raise _cdas_http_error(exc) from exc
