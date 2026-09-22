from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session, joinedload

from core.access_control import (
    COMPANY_MANAGEMENT_ROLES,
    LENDING_ROLES,
    TenantContext,
    assert_branch_scope,
    get_user_context,
    require_tenant_roles,
)
from database.models.enums import UserRole
from database.models.origination import LoanContract
from database.session import get_db
from services.contract_email_otp_service import (
    request_signing_code,
    signing_status,
    verify_signing_code,
)


router = APIRouter(
    prefix="/contract-signing",
    tags=["Contract Signing"],
)

CONTRACT_SIGNING_ROLES = LENDING_ROLES | COMPANY_MANAGEMENT_ROLES | {
    UserRole.BRANCH_MANAGER,
    UserRole.RISK_MANAGER,
    UserRole.COMPLIANCE_OFFICER,
}


class EmailOtpVerifyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    otp: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")


def _contract(
    db: Session,
    *,
    context: TenantContext,
    contract_id: UUID,
    lock: bool = False,
) -> LoanContract:
    query = (
        db.query(LoanContract)
        .options(joinedload(LoanContract.loan))
        .filter(
            LoanContract.id == contract_id,
            LoanContract.company_id == context.company_id,
        )
    )
    if lock:
        query = query.with_for_update()
    contract = query.first()
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")
    assert_branch_scope(context, contract.loan.branch_id if contract.loan else None)
    return contract


@router.get("/contracts/{contract_id}/email-otp/status")
def email_otp_status(
    contract_id: UUID,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    require_tenant_roles(context, CONTRACT_SIGNING_ROLES)
    contract = _contract(db, context=context, contract_id=contract_id)
    return signing_status(db, contract)


@router.post("/contracts/{contract_id}/email-otp/request")
def request_email_otp(
    contract_id: UUID,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    require_tenant_roles(context, CONTRACT_SIGNING_ROLES)
    contract = _contract(db, context=context, contract_id=contract_id, lock=True)
    return request_signing_code(
        db,
        contract=contract,
        requested_by_user_id=context.user.id,
    )


@router.post("/contracts/{contract_id}/email-otp/verify")
def verify_email_otp(
    contract_id: UUID,
    payload: EmailOtpVerifyRequest,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    require_tenant_roles(context, CONTRACT_SIGNING_ROLES)
    contract = _contract(db, context=context, contract_id=contract_id, lock=True)
    return verify_signing_code(
        db,
        contract=contract,
        otp=payload.otp,
        verified_by_user_id=context.user.id,
    )
