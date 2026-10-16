from __future__ import annotations

from uuid import UUID, uuid4
from datetime import datetime, timedelta, timezone

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
from database.models.pad_signing import ContractPadSigningSession
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


class EmailOtpRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recipient_email: str | None = Field(default=None, max_length=320)


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
    payload: EmailOtpRequest | None = None,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    require_tenant_roles(context, CONTRACT_SIGNING_ROLES)
    contract = _contract(db, context=context, contract_id=contract_id, lock=True)
    return request_signing_code(
        db,
        contract=contract,
        requested_by_user_id=context.user.id,
        recipient_email=(payload.recipient_email if payload else None),
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


@router.get("/contracts/{contract_id}/pad/preflight")
def pad_capture_preflight(
    contract_id: UUID,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    """Read-only preparation. This endpoint never signs a contract.

    A later evidence-upload route MUST recheck all conditions under a row lock,
    bind the exact contract hash, and verify explicit signer consent.
    """
    require_tenant_roles(context, CONTRACT_SIGNING_ROLES)
    contract = _contract(db, context=context, contract_id=contract_id)
    reasons: list[str] = []
    if contract.borrower_signed_at is not None:
        reasons.append("borrower_already_signed")
    if contract.locked_at is not None or contract.status == "signed":
        reasons.append("contract_locked")
    if contract.pdf_file_id is None:
        reasons.append("contract_pdf_missing")
    if not contract.contract_hash:
        reasons.append("contract_hash_missing")
    return {
        "contract_id": str(contract.id),
        "contract_number": contract.contract_number,
        "contract_version": contract.version,
        "contract_hash": contract.contract_hash,
        "ready": not reasons,
        "blockers": reasons,
        "requires_identity_verification": True,
        "requires_explicit_signer_consent": True,
        "capture_is_signature": False,
    }


@router.post("/contracts/{contract_id}/pad/sessions", status_code=201)
def create_pad_signing_session(
    contract_id: UUID,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    """Create a short-lived candidate capture session; does NOT authorize signing."""
    require_tenant_roles(context, CONTRACT_SIGNING_ROLES)
    contract = _contract(db, context=context, contract_id=contract_id, lock=True)
    if (contract.borrower_signed_at is not None or contract.locked_at is not None
            or contract.status == "signed" or contract.pdf_file_id is None
            or not contract.contract_hash):
        raise HTTPException(status_code=409, detail="Contract cannot start pad capture")
    now = datetime.now(timezone.utc)
    row = ContractPadSigningSession(
        id=uuid4(),
        company_id=context.company_id,
        contract_id=contract.id,
        operator_user_id=context.user.id,
        contract_hash=contract.contract_hash,
        status="created",
        expires_at=now + timedelta(minutes=10),
    )
    db.add(row)
    db.commit()
    return {
        "session_id": str(row.id),
        "contract_id": str(contract.id),
        "contract_hash": contract.contract_hash,
        "status": "created",
        "expires_at": row.expires_at.isoformat(),
        "capture_enabled": False,
        "reason": "Identity verification, consent and evidence submission not yet implemented",
    }


@router.get("/contracts/{contract_id}/pad/sessions/{session_id}")
def pad_signing_session_status(
    contract_id: UUID,
    session_id: UUID,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    require_tenant_roles(context, CONTRACT_SIGNING_ROLES)
    contract = _contract(db, context=context, contract_id=contract_id)
    row = (
        db.query(ContractPadSigningSession)
        .filter(
            ContractPadSigningSession.id == session_id,
            ContractPadSigningSession.company_id == context.company_id,
            ContractPadSigningSession.contract_id == contract.id,
            ContractPadSigningSession.operator_user_id == context.user.id,
        )
        .one_or_none()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Signing session not found")
    expired = datetime.now(timezone.utc) >= row.expires_at
    return {
        "session_id": str(row.id),
        "contract_id": str(row.contract_id),
        "status": "expired" if expired and row.status == "created" else row.status,
        "expires_at": row.expires_at.isoformat() + "Z",
        "capture_enabled": False,
    }
