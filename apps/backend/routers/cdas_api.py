from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from core.access_control import TenantContext, get_tenant_context
from database.session import get_db
from integrations.cdas import CdasError, cdas_client
from services.cdas_analysis_history import (
    save_or_get_analysis_record,
    serialize_analysis_record,
)
from services.cdas_official_snapshot import normalize_official_cdas_snapshot


router = APIRouter(prefix="/cdas", tags=["CDAS Official API"])


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


@router.get("/employees/{employee_no}")
async def get_cdas_employee(
    employee_no: str,
    context: TenantContext = Depends(get_tenant_context),
):
    """Read the employee identity directly from the official CDAS API."""
    _require_company_member(context)
    try:
        return await cdas_client.employee_details(employee_no.strip())
    except CdasError as exc:
        raise _cdas_http_error(exc) from exc


@router.get("/employees/{employee_no}/affordability")
async def get_cdas_affordability(
    employee_no: str,
    context: TenantContext = Depends(get_tenant_context),
):
    """Read current CDAS affordability. No value is calculated locally."""
    _require_company_member(context)
    try:
        amount = await cdas_client.affordability(employee_no.strip())
        return {"employee_no": employee_no.strip(), "affordability": amount, "source": "CDAS_API"}
    except CdasError as exc:
        raise _cdas_http_error(exc) from exc


@router.get("/employees/{employee_no}/deductions")
async def get_cdas_deductions(
    employee_no: str,
    own_only: bool = Query(default=False),
    deduction_status: int | None = Query(default=None, ge=1, le=10),
    context: TenantContext = Depends(get_tenant_context),
):
    """Read all deductions or the connected company's deductions for a status."""
    _require_company_member(context)
    employee_no = employee_no.strip()
    try:
        if own_only:
            if deduction_status is None:
                raise HTTPException(
                    status_code=422,
                    detail="deduction_status is required when own_only=true",
                )
            items = await cdas_client.own_deductions(employee_no, deduction_status)
        else:
            items = await cdas_client.all_deductions(employee_no)
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
    _require_company_member(context)
    employee_no = payload.employee_no.strip()
    try:
        raw_snapshot = await cdas_client.refresh_employee_snapshot(
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
):
    """Register/update/review/approve/cancel using CDAS's documented RequestType contract."""
    _require_company_member(context)
    try:
        return await cdas_client.add_update_deduction(payload.to_cdas_payload())
    except CdasError as exc:
        raise _cdas_http_error(exc) from exc


@router.get("/employees/{employee_no}/active-approved-deductions")
async def get_active_and_approved_cdas_deductions(
    employee_no: str,
    context: TenantContext = Depends(get_tenant_context),
):
    _require_company_member(context)
    try:
        return await cdas_client.active_and_approved_deductions(employee_no.strip())
    except CdasError as exc:
        raise _cdas_http_error(exc) from exc


@router.post("/deductions/modify-active")
async def modify_active_cdas_deduction(
    payload: CdasModifyActiveDeductionRequest,
    context: TenantContext = Depends(get_tenant_context),
):
    _require_company_member(context)
    try:
        return await cdas_client.modify_active_deduction(payload.to_cdas_payload())
    except CdasError as exc:
        raise _cdas_http_error(exc) from exc


@router.post("/deductions/settle")
async def settle_cdas_deduction(
    payload: CdasSettleDeductionRequest,
    context: TenantContext = Depends(get_tenant_context),
):
    _require_company_member(context)
    try:
        return await cdas_client.settle_deduction(payload.to_cdas_payload())
    except CdasError as exc:
        raise _cdas_http_error(exc) from exc


@router.get("/documents")
async def get_cdas_document(
    year: int = Query(ge=2000, le=2200),
    month: int = Query(ge=1, le=12),
    document_type: int = Query(ge=1, le=2),
    context: TenantContext = Depends(get_tenant_context),
):
    _require_company_member(context)
    try:
        return await cdas_client.get_document(
            year=year,
            month=month,
            document_type=document_type,
        )
    except CdasError as exc:
        raise _cdas_http_error(exc) from exc
