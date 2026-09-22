from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, Awaitable

from fastapi import APIRouter, Depends, HTTPException, Path
from pydantic import BaseModel, Field

from core.access_control import TenantContext, get_tenant_context
from database.config.config import settings
from services.cdas_api_client import (
    CdasApiClient,
    CdasApiError,
    CdasConfigurationError,
    CdasDeductionStatus,
    CdasDocumentType,
    CdasTransportError,
)

router = APIRouter(prefix="/cdas", tags=["CDAS Official API"])

_cdas_client: CdasApiClient | None = None


class CdasOwnedDeductionsRequest(BaseModel):
    deduction_status: int = Field(default=int(CdasDeductionStatus.ACTIVE), ge=1, le=10)


class CdasRefreshRequest(CdasOwnedDeductionsRequest):
    include_owned_deductions: bool = True


class CdasAddUpdateDeductionRequest(BaseModel):
    request_type: int = Field(ge=1, le=10)
    deduction_id: int = Field(default=0, ge=0)
    employee_no: str = Field(min_length=1, max_length=100)
    loan_policy: int = Field(ge=0)
    item_code: str = Field(min_length=1, max_length=100)
    deduction_amount: float = Field(ge=0)
    total_installment: int = Field(ge=0)
    principal_amount: float = Field(ge=0)
    effective_month: str = Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")
    reference_no: str = Field(min_length=1, max_length=200)


class CdasModifyActiveDeductionRequest(BaseModel):
    employee_no: str = Field(min_length=1, max_length=100)
    item_code: str = Field(min_length=1, max_length=100)
    total_installment: int = Field(ge=0)
    deduction_amount: float = Field(ge=0)
    principal_amount: float = Field(ge=0)
    effective_date: date


class CdasSettleDeductionRequest(BaseModel):
    item_code: str = Field(min_length=1, max_length=100)
    employee_no: str = Field(min_length=1, max_length=100)
    effective_date: datetime
    settlement_reason: int = Field(ge=1, le=4)


class CdasDocumentRequest(BaseModel):
    year: int = Field(ge=2000, le=2200)
    month: int = Field(ge=1, le=12)
    document_type: int = Field(
        default=int(CdasDocumentType.STATEMENT),
        ge=int(CdasDocumentType.OUTPUT_FILE),
        le=int(CdasDocumentType.STATEMENT),
    )


def _require_company_member(context: TenantContext) -> None:
    if context.is_platform_admin or not context.company_id or not context.staff:
        raise HTTPException(status_code=403, detail="A company-scoped membership is required")


def get_cdas_client() -> CdasApiClient:
    global _cdas_client
    if _cdas_client is None:
        _cdas_client = CdasApiClient()
    return _cdas_client


async def close_cdas_client() -> None:
    global _cdas_client
    if _cdas_client is not None:
        await _cdas_client.aclose()
        _cdas_client = None


def _clean_employee_no(employee_no: str) -> str:
    cleaned = employee_no.strip()
    if not cleaned:
        raise HTTPException(status_code=422, detail="Employee number is required")
    return cleaned


def _upstream_http_status(cdas_status: int) -> int:
    if cdas_status == 429:
        return 429
    if cdas_status == 404:
        return 404
    if cdas_status == 400:
        return 400
    if 495 <= cdas_status <= 499:
        return 422
    # Authentication/token errors belong to the server-to-server integration,
    # not to the logged-in LoanHub user's session.
    if cdas_status in {401, 402, 406, 417, 419}:
        return 502
    return 502


async def _cdas_result(call: Awaitable[Any]) -> Any:
    try:
        return await call
    except CdasConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except CdasTransportError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except CdasApiError as exc:
        raise HTTPException(
            status_code=_upstream_http_status(exc.status_code),
            detail={
                "provider": "CDAS",
                "cdas_status": exc.status_code,
                "message": exc.message,
            },
        ) from exc


@router.get("/status")
def cdas_status(context: TenantContext = Depends(get_tenant_context)) -> dict[str, Any]:
    _require_company_member(context)
    client = get_cdas_client()
    return {
        "enabled": settings.CDAS_ENABLED,
        "configured": client.configured,
        "daily_request_limit": settings.CDAS_DAILY_REQUEST_LIMIT,
        "documentation_version": "1.5",
        "credentials_exposed": False,
    }


@router.post("/employees/{employee_no}/details")
async def employee_details(
    employee_no: str = Path(min_length=1, max_length=100),
    context: TenantContext = Depends(get_tenant_context),
) -> Any:
    _require_company_member(context)
    employee_no = _clean_employee_no(employee_no)
    return await _cdas_result(get_cdas_client().get_employee(employee_no))


@router.post("/employees/{employee_no}/affordability")
async def employee_affordability(
    employee_no: str = Path(min_length=1, max_length=100),
    context: TenantContext = Depends(get_tenant_context),
) -> Any:
    _require_company_member(context)
    employee_no = _clean_employee_no(employee_no)
    return await _cdas_result(get_cdas_client().check_affordability(employee_no))


@router.post("/employees/{employee_no}/deductions/all")
async def employee_all_deductions(
    employee_no: str = Path(min_length=1, max_length=100),
    context: TenantContext = Depends(get_tenant_context),
) -> Any:
    _require_company_member(context)
    employee_no = _clean_employee_no(employee_no)
    return await _cdas_result(get_cdas_client().view_all_deductions(employee_no))


@router.post("/employees/{employee_no}/deductions/owned")
async def employee_owned_deductions(
    payload: CdasOwnedDeductionsRequest,
    employee_no: str = Path(min_length=1, max_length=100),
    context: TenantContext = Depends(get_tenant_context),
) -> Any:
    _require_company_member(context)
    employee_no = _clean_employee_no(employee_no)
    return await _cdas_result(
        get_cdas_client().view_deductions(employee_no, payload.deduction_status)
    )


@router.post("/employees/{employee_no}/active-approved")
async def employee_active_approved_deductions(
    employee_no: str = Path(min_length=1, max_length=100),
    context: TenantContext = Depends(get_tenant_context),
) -> Any:
    _require_company_member(context)
    employee_no = _clean_employee_no(employee_no)
    return await _cdas_result(
        get_cdas_client().get_active_and_approved_deduction(employee_no)
    )


@router.post("/employees/{employee_no}/refresh")
async def refresh_employee_cdas(
    payload: CdasRefreshRequest,
    employee_no: str = Path(min_length=1, max_length=100),
    context: TenantContext = Depends(get_tenant_context),
) -> dict[str, Any]:
    """Deliberately refresh one employee's official CDAS snapshot.

    This endpoint is POST rather than GET so LoanHub/browser caches do not turn
    a user-requested external refresh into an implicit background read. One
    invocation consumes three CDAS reads, or four when own deductions are
    included, so the frontend should show the fetched timestamp and avoid
    polling/reloading this endpoint automatically.
    """

    _require_company_member(context)
    employee_no = _clean_employee_no(employee_no)
    client = get_cdas_client()

    employee = await _cdas_result(client.get_employee(employee_no))
    affordability = await _cdas_result(client.check_affordability(employee_no))
    all_deductions = await _cdas_result(client.view_all_deductions(employee_no))
    owned_deductions: Any = None
    if payload.include_owned_deductions:
        owned_deductions = await _cdas_result(
            client.view_deductions(employee_no, payload.deduction_status)
        )

    return {
        "employee_no": employee_no,
        "employee": employee,
        "affordability": affordability,
        "all_deductions": all_deductions,
        "owned_deductions": owned_deductions,
        "owned_deduction_status": payload.deduction_status,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "source": "CDAS_API",
    }


@router.post("/deductions/workflow")
async def add_update_deduction(
    payload: CdasAddUpdateDeductionRequest,
    context: TenantContext = Depends(get_tenant_context),
) -> Any:
    _require_company_member(context)
    return await _cdas_result(
        get_cdas_client().add_update_deduction(
            request_type=payload.request_type,
            deduction_id=payload.deduction_id,
            employee_no=payload.employee_no.strip(),
            loan_policy=payload.loan_policy,
            item_code=payload.item_code.strip(),
            deduction_amount=payload.deduction_amount,
            total_installment=payload.total_installment,
            principal_amount=payload.principal_amount,
            effective_month=payload.effective_month,
            reference_no=payload.reference_no.strip(),
        )
    )


@router.post("/deductions/{deduction_id}/modify-active")
async def modify_active_deduction(
    payload: CdasModifyActiveDeductionRequest,
    deduction_id: int = Path(ge=1),
    context: TenantContext = Depends(get_tenant_context),
) -> Any:
    _require_company_member(context)
    return await _cdas_result(
        get_cdas_client().modify_active_deduction(
            employee_no=payload.employee_no.strip(),
            item_code=payload.item_code.strip(),
            total_installment=payload.total_installment,
            deduction_amount=payload.deduction_amount,
            principal_amount=payload.principal_amount,
            deduction_id=deduction_id,
            effective_date=payload.effective_date.isoformat(),
        )
    )


@router.post("/deductions/{deduction_id}/settle")
async def settle_deduction(
    payload: CdasSettleDeductionRequest,
    deduction_id: int = Path(ge=1),
    context: TenantContext = Depends(get_tenant_context),
) -> Any:
    _require_company_member(context)
    return await _cdas_result(
        get_cdas_client().settle_deduction(
            item_code=payload.item_code.strip(),
            deduction_id=deduction_id,
            effective_date=payload.effective_date.isoformat(),
            employee_no=payload.employee_no.strip(),
            settlement_reason=payload.settlement_reason,
        )
    )


@router.post("/documents")
async def get_cdas_document(
    payload: CdasDocumentRequest,
    context: TenantContext = Depends(get_tenant_context),
) -> Any:
    _require_company_member(context)
    return await _cdas_result(
        get_cdas_client().get_document(
            year=payload.year,
            month=payload.month,
            document_type=payload.document_type,
        )
    )
