from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from core.access_control import (
    COMPANY_MANAGEMENT_ROLES,
    FINANCE_ROLES,
    TRANSPARENCY_ROLES,
    TenantContext,
    get_tenant_context,
    require_platform_finance,
    require_platform_owner,
    require_tenant_roles,
)
from database.models.finance import (
    BorrowerFeeConfiguration,
    CompanyAccountOpeningFeeConfiguration,
    PlatformChargeClaim,
    TransactionChargeAgreement,
    TransactionChargeLedgerEntry,
)
from database.models.company import LoanCompany
from database.models.enums import PaymentProvider
from database.models.user import User
from database.schemas.cash import CashPaymentResult
from database.schemas.finance import (
    AccountOpeningFeeRead,
    AccountOpeningFeeWrite,
    AgreementDecision,
    ClaimCashSettlementCreate,
    ClaimCompanyDecision,
    BorrowerRequestFeeRead,
    BorrowerRequestFeeWrite,
    ChargeClaimCreate,
    ChargeClaimRead,
    ChargeLedgerRead,
    TransactionAgreementRead,
    TransactionAgreementWrite,
)
from database.session import get_db
from services.platform_finance_service import agreement_number, create_charge_claim, record_claim_settlement

router = APIRouter(prefix="/finance-config", tags=["Cash Finance Configuration"])


def _deactivate_matching_fee(db: Session, model, company_id: UUID | None, exclude_id: UUID | None = None) -> None:
    query = db.query(model)
    query = query.filter(model.company_id == company_id) if company_id else query.filter(model.company_id.is_(None))
    if exclude_id:
        query = query.filter(model.id != exclude_id)
    query.update({model.is_active: False}, synchronize_session=False)


@router.get("/borrower-request-fees", response_model=list[BorrowerRequestFeeRead])
def list_borrower_request_fees(
    db: Session = Depends(get_db),
    _: User = Depends(require_platform_finance),
):
    return db.query(BorrowerFeeConfiguration).order_by(BorrowerFeeConfiguration.created_at.desc()).all()


@router.post("/borrower-request-fees", response_model=BorrowerRequestFeeRead, status_code=201)
def create_borrower_request_fee(
    payload: BorrowerRequestFeeWrite,
    db: Session = Depends(get_db),
    owner: User = Depends(require_platform_owner),
):
    if payload.company_id and not db.get(LoanCompany, payload.company_id):
        raise HTTPException(404, "Company not found")
    if payload.is_active:
        _deactivate_matching_fee(db, BorrowerFeeConfiguration, payload.company_id)
    item = BorrowerFeeConfiguration(
        **payload.model_dump(),
        allowed_providers=[PaymentProvider.CASH.value],
        created_by_user_id=owner.id,
    )
    db.add(item); db.commit(); db.refresh(item)
    return item


@router.put("/borrower-request-fees/{fee_id}", response_model=BorrowerRequestFeeRead)
def update_borrower_request_fee(
    fee_id: UUID,
    payload: BorrowerRequestFeeWrite,
    db: Session = Depends(get_db),
    _: User = Depends(require_platform_owner),
):
    item = db.get(BorrowerFeeConfiguration, fee_id)
    if not item:
        raise HTTPException(404, "Borrower request fee configuration not found")
    if payload.is_active:
        _deactivate_matching_fee(db, BorrowerFeeConfiguration, payload.company_id, item.id)
    for key, value in payload.model_dump().items():
        setattr(item, key, value)
    item.allowed_providers = [PaymentProvider.CASH.value]
    db.commit(); db.refresh(item)
    return item


@router.get("/account-opening-fees", response_model=list[AccountOpeningFeeRead])
def list_account_opening_fees(
    db: Session = Depends(get_db),
    _: User = Depends(require_platform_finance),
):
    return db.query(CompanyAccountOpeningFeeConfiguration).order_by(CompanyAccountOpeningFeeConfiguration.created_at.desc()).all()


@router.post("/account-opening-fees", response_model=AccountOpeningFeeRead, status_code=201)
def create_account_opening_fee(
    payload: AccountOpeningFeeWrite,
    db: Session = Depends(get_db),
    owner: User = Depends(require_platform_owner),
):
    if payload.company_id and not db.get(LoanCompany, payload.company_id):
        raise HTTPException(404, "Company not found")
    if payload.is_active:
        _deactivate_matching_fee(db, CompanyAccountOpeningFeeConfiguration, payload.company_id)
    item = CompanyAccountOpeningFeeConfiguration(
        **payload.model_dump(),
        required_before_activation=False,
        allowed_providers=[PaymentProvider.CASH.value],
        created_by_user_id=owner.id,
    )
    db.add(item); db.commit(); db.refresh(item)
    return item


@router.put("/account-opening-fees/{fee_id}", response_model=AccountOpeningFeeRead)
def update_account_opening_fee(
    fee_id: UUID,
    payload: AccountOpeningFeeWrite,
    db: Session = Depends(get_db),
    _: User = Depends(require_platform_owner),
):
    item = db.get(CompanyAccountOpeningFeeConfiguration, fee_id)
    if not item:
        raise HTTPException(404, "Account-opening fee configuration not found")
    if payload.is_active:
        _deactivate_matching_fee(db, CompanyAccountOpeningFeeConfiguration, payload.company_id, item.id)
    for key, value in payload.model_dump().items():
        setattr(item, key, value)
    item.required_before_activation = False
    item.allowed_providers = [PaymentProvider.CASH.value]
    db.commit(); db.refresh(item)
    return item


@router.get("/agreements", response_model=list[TransactionAgreementRead])
def list_agreements(
    company_id: UUID | None = Query(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(require_platform_finance),
):
    query = db.query(TransactionChargeAgreement)
    if company_id:
        query = query.filter(TransactionChargeAgreement.company_id == company_id)
    return query.order_by(TransactionChargeAgreement.created_at.desc()).all()


@router.post("/agreements", response_model=TransactionAgreementRead, status_code=201)
def create_agreement(
    payload: TransactionAgreementWrite,
    db: Session = Depends(get_db),
    owner: User = Depends(require_platform_owner),
):
    if not db.get(LoanCompany, payload.company_id):
        raise HTTPException(404, "Company not found")
    item = TransactionChargeAgreement(
        **payload.model_dump(),
        agreement_number=agreement_number(),
        status="draft",
    )
    db.add(item); db.commit(); db.refresh(item)
    return item


@router.put("/agreements/{agreement_id}", response_model=TransactionAgreementRead)
def update_agreement(
    agreement_id: UUID,
    payload: TransactionAgreementWrite,
    db: Session = Depends(get_db),
    _: User = Depends(require_platform_owner),
):
    item = db.get(TransactionChargeAgreement, agreement_id)
    if not item:
        raise HTTPException(404, "Agreement not found")
    if item.status == "active":
        raise HTTPException(409, "Create a revised agreement instead of editing an active financial agreement")
    for key, value in payload.model_dump().items():
        setattr(item, key, value)
    db.commit(); db.refresh(item)
    return item


@router.post("/agreements/{agreement_id}/owner-decision", response_model=TransactionAgreementRead)
def owner_decision(
    agreement_id: UUID,
    payload: AgreementDecision,
    db: Session = Depends(get_db),
    owner: User = Depends(require_platform_owner),
):
    item = db.get(TransactionChargeAgreement, agreement_id)
    if not item:
        raise HTTPException(404, "Agreement not found")
    now = datetime.now(timezone.utc)
    if payload.accept:
        item.owner_accepted_by_user_id = owner.id
        item.owner_accepted_at = now
        if item.company_accepted_at:
            item.status = "active"; item.activated_at = now
        else:
            item.status = "owner_accepted"
    else:
        item.status = "rejected"; item.suspended_at = now
    db.commit(); db.refresh(item)
    return item


@router.post("/agreements/{agreement_id}/company-decision", response_model=TransactionAgreementRead)
def company_decision(
    agreement_id: UUID,
    payload: AgreementDecision,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(context, COMPANY_MANAGEMENT_ROLES)
    item = db.get(TransactionChargeAgreement, agreement_id)
    if not item or item.company_id != context.company_id:
        raise HTTPException(404, "Agreement not found")
    now = datetime.now(timezone.utc)
    if payload.accept:
        item.company_accepted_by_user_id = context.user.id
        item.company_accepted_at = now
        if item.owner_accepted_at:
            item.status = "active"; item.activated_at = now
        else:
            item.status = "company_accepted"
    else:
        item.status = "rejected"; item.suspended_at = now
    db.commit(); db.refresh(item)
    return item


@router.get("/charge-ledger", response_model=list[ChargeLedgerRead])
def list_charge_ledger(
    company_id: UUID | None = Query(default=None),
    limit: int = Query(default=500, ge=1, le=2000),
    db: Session = Depends(get_db),
    _: User = Depends(require_platform_finance),
):
    query = db.query(TransactionChargeLedgerEntry)
    if company_id:
        query = query.filter(TransactionChargeLedgerEntry.company_id == company_id)
    return query.order_by(TransactionChargeLedgerEntry.accrued_at.desc()).limit(limit).all()


@router.get("/claims", response_model=list[ChargeClaimRead])
def list_claims(
    company_id: UUID | None = Query(default=None),
    db: Session = Depends(get_db),
    _: User = Depends(require_platform_finance),
):
    query = db.query(PlatformChargeClaim)
    if company_id:
        query = query.filter(PlatformChargeClaim.company_id == company_id)
    return query.order_by(PlatformChargeClaim.created_at.desc()).all()


@router.post("/claims", response_model=ChargeClaimRead, status_code=status.HTTP_201_CREATED)
def create_claim(
    payload: ChargeClaimCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_platform_finance),
):
    claim = create_charge_claim(
        db,
        company_id=payload.company_id,
        period_start=payload.period_start,
        period_end=payload.period_end,
        due_days=payload.due_days,
        issued_by_user_id=user.id,
        notes=payload.notes,
    )
    db.commit(); db.refresh(claim)
    return claim


@router.get("/company/agreements", response_model=list[TransactionAgreementRead])
def list_company_agreements(
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(context, TRANSPARENCY_ROLES | FINANCE_ROLES | COMPANY_MANAGEMENT_ROLES)
    return (
        db.query(TransactionChargeAgreement)
        .filter(TransactionChargeAgreement.company_id == context.company_id)
        .order_by(TransactionChargeAgreement.created_at.desc())
        .all()
    )


@router.get("/company/charge-ledger", response_model=list[ChargeLedgerRead])
def list_company_charge_ledger(
    limit: int = Query(default=500, ge=1, le=2000),
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(context, TRANSPARENCY_ROLES | FINANCE_ROLES | COMPANY_MANAGEMENT_ROLES)
    return (
        db.query(TransactionChargeLedgerEntry)
        .filter(TransactionChargeLedgerEntry.company_id == context.company_id)
        .order_by(TransactionChargeLedgerEntry.accrued_at.desc())
        .limit(limit)
        .all()
    )


@router.get("/company/claims", response_model=list[ChargeClaimRead])
def list_company_claims(
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(context, TRANSPARENCY_ROLES | FINANCE_ROLES | COMPANY_MANAGEMENT_ROLES)
    return (
        db.query(PlatformChargeClaim)
        .filter(PlatformChargeClaim.company_id == context.company_id)
        .order_by(PlatformChargeClaim.created_at.desc())
        .all()
    )


@router.post("/claims/{claim_id}/company-decision", response_model=ChargeClaimRead)
def decide_company_claim(
    claim_id: UUID,
    payload: ClaimCompanyDecision,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(context, FINANCE_ROLES | COMPANY_MANAGEMENT_ROLES)
    claim = (
        db.query(PlatformChargeClaim)
        .filter(PlatformChargeClaim.id == claim_id, PlatformChargeClaim.company_id == context.company_id)
        .with_for_update()
        .first()
    )
    if not claim:
        raise HTTPException(404, "Claim not found")
    if claim.status not in {"issued", "acknowledged", "disputed"}:
        raise HTTPException(409, "This claim cannot be changed in its current state")
    now = datetime.now(timezone.utc)
    if payload.action == "acknowledge":
        claim.status = "acknowledged"
        claim.acknowledged_at = now
        claim.acknowledged_by_user_id = context.user.id
        claim.dispute_reason = None
        claim.disputed_at = None
    else:
        if not payload.reason or not payload.reason.strip():
            raise HTTPException(422, "A dispute reason is required")
        claim.status = "disputed"
        claim.disputed_at = now
        claim.dispute_reason = payload.reason.strip()
    db.commit(); db.refresh(claim)
    return claim


@router.post("/claims/{claim_id}/settle", response_model=CashPaymentResult)
@router.post("/claims/{claim_id}/cash-settle", response_model=CashPaymentResult, include_in_schema=False)
def settle_company_claim(
    claim_id: UUID,
    payload: ClaimCashSettlementCreate,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(context, FINANCE_ROLES | COMPANY_MANAGEMENT_ROLES)
    claim = (
        db.query(PlatformChargeClaim)
        .filter(PlatformChargeClaim.id == claim_id, PlatformChargeClaim.company_id == context.company_id)
        .with_for_update()
        .first()
    )
    if not claim:
        raise HTTPException(404, "Claim not found")
    payment, cash = record_claim_settlement(
        db,
        claim=claim,
        initiated_by_user_id=context.user.id,
        payment_method=payload.payment_method,
        proof_reference=payload.proof_reference,
        proof_url=payload.proof_url,
        proof_notes=payload.proof_notes,
        notes=payload.notes,
        idempotency_key=payload.idempotency_key,
    )
    return {
        "payment_id": payment.id,
        "payment_method": payment.payment_method,
        "provider_reference": payment.provider_reference,
        "proof_reference": payment.proof_reference,
        "cash_transaction": cash,
        "preview": None,
    }
