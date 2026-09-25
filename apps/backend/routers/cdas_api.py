from __future__ import annotations

from typing import Literal

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
from database.session import get_db
from integrations.cdas import CdasError
from services.cdas_config_service import (
    configuration_summary,
    get_company_cdas_client,
    get_configuration,
    test_company_configuration,
    update_configuration,
)

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


def _require_company_manager(context: TenantContext) -> None:
    if context.is_platform_admin or not context.company_id or not context.staff:
        raise HTTPException(status_code=403, detail="A company-scoped membership is required")
    require_tenant_roles(context, COMPANY_MANAGEMENT_ROLES)


def _require_lending_user(context: TenantContext) -> None:
    if context.is_platform_admin or not context.company_id or not context.staff:
        raise HTTPException(status_code=403, detail="A company-scoped membership is required")
    require_tenant_roles(context, LENDING_ROLES)


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


@router.post("/employees/verify")
async def verify_cdas_employee(
    payload: CdasEmployeeLookupRequest,
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
):
    """Phase 2: perform one deliberate CDAS employee lookup."""

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
    """Phase 3: perform one deliberate CDAS affordability check."""

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
    """Phase 4: view all third-party deductions for one employee."""

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
    """Phase 4: view the authenticated third party's deductions by status."""

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
    """Phase 4: fetch the employee's active/approved deduction record."""

    _require_lending_user(context)
    assert context.company_id is not None
    try:
        client = get_company_cdas_client(db, context.company_id)
        deduction = await client.get_active_and_approved_deduction(payload.employee_no)
    except CdasError as exc:
        raise _cdas_http_error(exc) from exc
    return {"ok": True, "deduction": deduction}
