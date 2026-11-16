from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from core.access_control import (
    COMPANY_MANAGEMENT_ROLES,
    TenantContext,
    get_user_context,
    require_tenant_roles,
)
from database.models.company_loan_settings import CompanyLoanSettings
from database.models.legacy_loan_capture import LegacyLoanCapture
from services.legacy_loan_lock_policy import legacy_loan_lock_enabled
from services.legacy_loan_lock_transition import transition_legacy_loan_lock
from database.session import get_db


router = APIRouter(prefix="/loan-settings", tags=["Company Loan Settings"])

ContractTemplateStyle = Literal["loanhub_standard", "filizwa_style"]
CONTRACT_TEMPLATE_STYLES: tuple[tuple[str, str], ...] = (
    ("loanhub_standard", "LoanHub Standard"),
    ("filizwa_style", "Filizwa Financial"),
)


class LoanSettingsUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    default_contract_template_style: ContractTemplateStyle = "loanhub_standard"


class LoanSettingsResponse(LoanSettingsUpdate):
    id: str
    company_id: str


class ContractTemplateStyleResponse(BaseModel):
    value: ContractTemplateStyle
    label: str


def _get_or_create_settings(db: Session, company_id) -> CompanyLoanSettings:
    row = (
        db.query(CompanyLoanSettings)
        .filter(CompanyLoanSettings.company_id == company_id)
        .first()
    )
    if row:
        return row

    row = CompanyLoanSettings(company_id=company_id)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _response(row: CompanyLoanSettings) -> dict[str, str]:
    return {
        "id": str(row.id),
        "company_id": str(row.company_id),
        "default_contract_template_style": row.default_contract_template_style,
    }


@router.get("", response_model=LoanSettingsResponse)
def get_loan_settings(
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    return _response(_get_or_create_settings(db, context.company_id))


@router.put("", response_model=LoanSettingsResponse)
def update_loan_settings(
    payload: LoanSettingsUpdate,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    require_tenant_roles(context, COMPANY_MANAGEMENT_ROLES)
    row = _get_or_create_settings(db, context.company_id)
    row.default_contract_template_style = payload.default_contract_template_style
    db.commit()
    db.refresh(row)
    return _response(row)


@router.get("/contract-template-styles", response_model=list[ContractTemplateStyleResponse])
def list_contract_template_styles(
    _context: TenantContext = Depends(get_user_context),
):
    return [
        {"value": value, "label": label}
        for value, label in CONTRACT_TEMPLATE_STYLES
    ]


class LegacyLoanLockStatusResponse(BaseModel):
    company_id: str
    enabled: bool
    legacy_capture_count: int
    activation_available: bool
    activation_note: str


@router.get("/legacy-loan-lock", response_model=LegacyLoanLockStatusResponse)
def get_legacy_loan_lock_status(
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    """Read-only company-scoped lock status; activation remains unavailable."""
    require_tenant_roles(context, COMPANY_MANAGEMENT_ROLES)
    count = (
        db.query(LegacyLoanCapture)
        .filter(LegacyLoanCapture.company_id == context.company_id)
        .count()
    )
    return {
        "company_id": str(context.company_id),
        "enabled": legacy_loan_lock_enabled(db, context.company_id),
        "legacy_capture_count": count,
        "activation_available": False,
        "activation_note": "Activation requires complete financial mutation-path audit and deployment validation.",
    }


@router.post("/legacy-loan-lock/disable", response_model=LegacyLoanLockStatusResponse)
def disable_legacy_loan_lock(
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    """Authorized emergency unlock; enabling is not yet available."""
    require_tenant_roles(context, COMPANY_MANAGEMENT_ROLES)
    transition_legacy_loan_lock(
        db,
        company_id=context.company_id,
        actor_user_id=context.user.id,
        actor_role=context.role.value,
        enabled=False,
    )
    return get_legacy_loan_lock_status(db=db, context=context)
