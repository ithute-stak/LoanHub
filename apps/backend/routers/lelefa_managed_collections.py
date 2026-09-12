from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session, joinedload

from core.access_control import (
    COLLECTIONS_ROLES,
    COMPANY_MANAGEMENT_ROLES,
    TenantContext,
    assert_branch_scope,
    get_tenant_context,
    require_tenant_roles,
)
from database.models.borrower import Borrower
from database.models.client_loan_company import ClientCompanyLoan
from database.models.company_operating_system import CompanyOperatingRecord
from database.models.lending_operations import CollectionCase
from database.models.origination import OriginationIntegrationConfiguration
from database.models.user import User
from database.session import get_db
from services.lelefa_managed_collections import (
    BRIDGE_TOKEN_HEADER,
    DEFAULT_RULES,
    IDEMPOTENCY_HEADER,
    INTEGRATION_TYPE,
    PROVIDER,
    RECORD_MODULE,
    RECORD_TYPE,
    bridge_token_matches,
    delivery_state,
    eligible_case,
    integration_base_url,
    new_bridge_token,
    normalize_rules,
    post_to_lelefa,
)


router = APIRouter(prefix="/lelefa-collections", tags=["Lelefa Managed Collections"])


class LelefaRulesUpdate(BaseModel):
    min_days_past_due: int = Field(default=120, ge=1, le=3650)
    min_overdue_amount: Decimal = Field(default=Decimal("0"), ge=0)
    min_outstanding_balance: Decimal = Field(default=Decimal("0"), ge=0)
    stages: list[str] = Field(default_factory=list, max_length=20)
    priorities: list[str] = Field(default_factory=list, max_length=20)
    exclude_active_promises: bool = True
    exclude_legal_handover: bool = False
    share_national_id: bool = False
    share_employment: bool = False


class LelefaSettingsUpdate(BaseModel):
    enabled: bool
    rules: LelefaRulesUpdate = Field(default_factory=LelefaRulesUpdate)


class LelefaReferralCreate(BaseModel):
    case_ids: list[UUID] = Field(min_length=1, max_length=500)
    note: str | None = Field(default=None, max_length=2000)


class LelefaReferralVerification(BaseModel):
    referral_id: UUID
    referral_reference: str = Field(min_length=1, max_length=100)
    company_id: UUID


class LelefaOfferDecision(BaseModel):
    decision: Literal["accept", "reject"]
    notes: str | None = Field(default=None, max_length=2000)


class LelefaOfferPayload(BaseModel):
    offer_id: str = Field(min_length=1, max_length=100)
    status: str = Field(default="offered", max_length=40)
    commission_percent: Decimal = Field(ge=0, le=100)
    onboarding_fee: Decimal = Field(default=Decimal("0"), ge=0)
    legal_action_fee: Decimal = Field(default=Decimal("0"), ge=0)
    max_settlement_discount_percent: Decimal = Field(default=Decimal("0"), ge=0, le=100)
    engagement_term_months: int = Field(default=6, ge=1, le=120)
    valid_until: str | None = None
    reporting_cadence: str = Field(default="monthly", max_length=80)
    service_terms: dict[str, Any] = Field(default_factory=dict)
    notes: str | None = Field(default=None, max_length=5000)
    sent_at: str | None = None


class LelefaOfferCallback(BaseModel):
    referral_reference: str = Field(min_length=1, max_length=100)
    remote_referral_id: str | None = Field(default=None, max_length=100)
    offer: LelefaOfferPayload


def _configuration(db: Session, company_id: UUID) -> OriginationIntegrationConfiguration | None:
    return (
        db.query(OriginationIntegrationConfiguration)
        .filter(
            OriginationIntegrationConfiguration.company_id == company_id,
            OriginationIntegrationConfiguration.provider == PROVIDER,
        )
        .one_or_none()
    )


def _settings_payload(row: OriginationIntegrationConfiguration | None) -> dict[str, Any]:
    rules = normalize_rules(row.configuration if row else None)
    return {
        "enabled": bool(row and row.is_enabled),
        "provider": PROVIDER,
        "integration_type": INTEGRATION_TYPE,
        "selection_mode": "rule_assisted_manual_approval",
        "rules": rules,
        "bridge_configured": True,
        "bridge_status": "ithute_internal_ready",
        "provider_endpoint": integration_base_url(),
        "privacy": {
            "share_bank_account_numbers": False,
            "share_documents_automatically": False,
            "share_national_id": bool(rules["share_national_id"]),
            "share_employment": bool(rules["share_employment"]),
        },
    }


def _company_cases(db: Session, context: TenantContext) -> list[CollectionCase]:
    query = db.query(CollectionCase).filter(CollectionCase.company_id == context.company_id)
    if context.branch_id and context.role not in COMPANY_MANAGEMENT_ROLES:
        query = query.filter(CollectionCase.branch_id == context.branch_id)
    return query.order_by(CollectionCase.days_past_due.desc(), CollectionCase.outstanding_balance.desc()).all()


def _loan_map(db: Session, cases: list[CollectionCase]) -> dict[UUID, ClientCompanyLoan]:
    loan_ids = [case.loan_id for case in cases]
    if not loan_ids:
        return {}
    loans = (
        db.query(ClientCompanyLoan)
        .options(
            joinedload(ClientCompanyLoan.borrower)
            .joinedload(Borrower.user)
            .joinedload(User.person)
        )
        .filter(ClientCompanyLoan.id.in_(loan_ids))
        .all()
    )
    return {loan.id: loan for loan in loans}


def _enum(value: Any) -> str:
    return str(getattr(value, "value", value or ""))


def _case_snapshot(case: CollectionCase, loan: ClientCompanyLoan, rules: dict[str, Any]) -> dict[str, Any]:
    borrower = loan.borrower
    user = borrower.user
    person = user.person
    full_name = person.full_name if person else (user.email or user.phone or "Borrower")
    snapshot: dict[str, Any] = {
        "collection_case_id": str(case.id),
        "case_reference": case.case_reference,
        "borrower_id": str(case.borrower_id),
        "loan_id": str(case.loan_id),
        "loan_reference": loan.loan_reference,
        "loan_status": _enum(loan.status),
        "borrower_name": full_name,
        "phone": user.phone,
        "email": user.email,
        "physical_address": person.physical_address if person else None,
        "district": person.district if person else None,
        "town_or_village": person.town_or_village if person else None,
        "days_past_due": int(case.days_past_due or 0),
        "overdue_amount": float(case.overdue_amount or 0),
        "outstanding_balance": float(case.outstanding_balance or 0),
        "priority": case.priority,
        "stage": case.stage,
        "case_status": case.status,
        "promise_status": case.promise_status,
        "promise_amount": float(case.promise_amount) if case.promise_amount is not None else None,
        "promise_date": case.promise_date.isoformat() if case.promise_date else None,
        "legal_handover_at": case.legal_handover_at.isoformat() if case.legal_handover_at else None,
        "loan_principal_amount": float(loan.principal_amount or 0),
        "loan_amount_paid": float(loan.amount_paid or 0),
        "loan_disbursed_at": loan.disbursed_at.isoformat() if loan.disbursed_at else None,
    }
    if rules["share_national_id"]:
        snapshot["national_id"] = person.national_id if person else None
        snapshot["passport_number"] = person.passport_number if person else None
    if rules["share_employment"]:
        snapshot["employment_status"] = _enum(borrower.employment_status)
        snapshot["employer_name"] = borrower.employer_name
        snapshot["job_title"] = borrower.job_title
    return snapshot


def _already_referred_case_ids(db: Session, company_id: UUID) -> set[str]:
    rows = (
        db.query(CompanyOperatingRecord)
        .filter(
            CompanyOperatingRecord.company_id == company_id,
            CompanyOperatingRecord.module == RECORD_MODULE,
            CompanyOperatingRecord.record_type == RECORD_TYPE,
            CompanyOperatingRecord.is_archived.is_(False),
        )
        .all()
    )
    result: set[str] = set()
    for row in rows:
        if row.status in {"rejected", "cancelled", "failed_delivery"}:
            continue
        for item in (row.data or {}).get("items", []):
            if item.get("collection_case_id"):
                result.add(str(item["collection_case_id"]))
    return result


def _record_payload(row: CompanyOperatingRecord) -> dict[str, Any]:
    public_data = dict(row.data or {})
    public_data.pop("bridge_token", None)
    return {
        "id": str(row.id),
        "reference": row.reference,
        "status": row.status,
        "title": row.title,
        "description": row.description,
        "amount": float(row.amount or 0),
        "currency": row.currency,
        "data": public_data,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def _stored_bridge_token(row: CompanyOperatingRecord) -> str:
    return str((row.data or {}).get("bridge_token") or "")


async def _deliver_referral(db: Session, row: CompanyOperatingRecord, context: TenantContext) -> None:
    data = dict(row.data or {})
    bridge_token = str(data.get("bridge_token") or "")
    if not bridge_token:
        bridge_token = new_bridge_token()
        data["bridge_token"] = bridge_token
    payload = {
        "schema_version": "1.1",
        "referral_id": str(row.id),
        "referral_reference": row.reference,
        "submitted_at": data.get("submitted_at"),
        "company": data.get("company", {}),
        "criteria": data.get("criteria", {}),
        "items": data.get("items", []),
        "note": data.get("note"),
        "bridge_token": bridge_token,
        "callback": {"system": "LoanHub", "referral_id": str(row.id)},
    }
    try:
        remote = await post_to_lelefa(
            "/api/v1/integrations/loanhub/referrals",
            payload,
            bridge_token=bridge_token,
            idempotency_key=f"loanhub-referral:{row.id}",
        )
        data["delivery"] = delivery_state("sent", remote=remote)
        data["remote_referral_id"] = remote.get("referral_id") or data.get("remote_referral_id")
        row.status = "received" if remote.get("status") in {"received", "under_review"} else "submitted"
    except Exception as exc:  # network failures must never discard the selected portfolio
        data["delivery"] = delivery_state("failed", message=str(exc)[:500])
        row.status = "failed_delivery"
    row.data = data
    db.commit()


@router.get("/settings")
def get_lelefa_collection_settings(
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(context, COLLECTIONS_ROLES)
    if not context.company_id:
        raise HTTPException(status_code=403, detail="An active company context is required")
    return _settings_payload(_configuration(db, context.company_id))


@router.put("/settings")
def update_lelefa_collection_settings(
    payload: LelefaSettingsUpdate,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(context, COMPANY_MANAGEMENT_ROLES)
    if not context.company_id:
        raise HTTPException(status_code=403, detail="An active company context is required")
    row = _configuration(db, context.company_id)
    if row is None:
        row = OriginationIntegrationConfiguration(
            company_id=context.company_id,
            provider=PROVIDER,
            environment="production",
            configured_by_user_id=context.user.id,
        )
        db.add(row)
    row.is_enabled = payload.enabled
    row.configuration = {
        "integration_type": INTEGRATION_TYPE,
        "selection_mode": "rule_assisted_manual_approval",
        "rules": normalize_rules(payload.rules.model_dump()),
    }
    row.configured_by_user_id = context.user.id
    db.commit()
    db.refresh(row)
    return _settings_payload(row)


@router.get("/candidates")
def list_lelefa_collection_candidates(
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(context, COLLECTIONS_ROLES)
    if not context.company_id:
        raise HTTPException(status_code=403, detail="An active company context is required")
    config = _configuration(db, context.company_id)
    rules = normalize_rules(config.configuration if config else DEFAULT_RULES)
    cases = _company_cases(db, context)
    loans = _loan_map(db, cases)
    referred = _already_referred_case_ids(db, context.company_id)
    candidates: list[dict[str, Any]] = []
    excluded = 0
    for case in cases:
        allowed, reasons = eligible_case(case, rules)
        loan = loans.get(case.loan_id)
        if not allowed or loan is None:
            excluded += 1
            continue
        item = _case_snapshot(case, loan, rules)
        item["already_referred"] = str(case.id) in referred
        item["eligible"] = True
        item["matched_rules"] = True
        item["exclusion_reasons"] = reasons
        candidates.append(item)
    return {
        "enabled": bool(config and config.is_enabled),
        "rules": rules,
        "candidate_count": len(candidates),
        "candidate_total_outstanding": sum(item["outstanding_balance"] for item in candidates if not item["already_referred"]),
        "excluded_case_count": excluded,
        "candidates": candidates,
    }


@router.get("/referrals")
def list_lelefa_referrals(
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(context, COLLECTIONS_ROLES)
    if not context.company_id:
        raise HTTPException(status_code=403, detail="An active company context is required")
    query = db.query(CompanyOperatingRecord).filter(
        CompanyOperatingRecord.company_id == context.company_id,
        CompanyOperatingRecord.module == RECORD_MODULE,
        CompanyOperatingRecord.record_type == RECORD_TYPE,
        CompanyOperatingRecord.is_archived.is_(False),
    )
    if context.branch_id and context.role not in COMPANY_MANAGEMENT_ROLES:
        query = query.filter(
            (CompanyOperatingRecord.branch_id == context.branch_id)
            | (CompanyOperatingRecord.branch_id.is_(None))
        )
    rows = query.order_by(CompanyOperatingRecord.created_at.desc()).all()
    return [_record_payload(row) for row in rows]


@router.post("/referrals", status_code=status.HTTP_201_CREATED)
async def create_lelefa_referral(
    payload: LelefaReferralCreate,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(context, COLLECTIONS_ROLES)
    if not context.company_id or not context.company:
        raise HTTPException(status_code=403, detail="An active company context is required")
    config = _configuration(db, context.company_id)
    if not config or not config.is_enabled:
        raise HTTPException(status_code=409, detail="Lelefa managed collections is switched off for this company")
    rules = normalize_rules(config.configuration)
    cases = (
        db.query(CollectionCase)
        .filter(
            CollectionCase.company_id == context.company_id,
            CollectionCase.id.in_(payload.case_ids),
        )
        .all()
    )
    if len(cases) != len(set(payload.case_ids)):
        raise HTTPException(status_code=404, detail="One or more selected collection cases were not found")
    referred = _already_referred_case_ids(db, context.company_id)
    loans = _loan_map(db, cases)
    items: list[dict[str, Any]] = []
    branch_ids: set[UUID] = set()
    for case in cases:
        assert_branch_scope(context, case.branch_id)
        allowed, reasons = eligible_case(case, rules)
        if not allowed:
            raise HTTPException(
                status_code=409,
                detail={"message": "A selected case no longer matches the company referral rules", "case_id": str(case.id), "reasons": reasons},
            )
        if str(case.id) in referred:
            raise HTTPException(status_code=409, detail=f"Collection case {case.case_reference} is already in an active Lelefa referral")
        loan = loans.get(case.loan_id)
        if loan is None:
            raise HTTPException(status_code=409, detail=f"Loan for collection case {case.case_reference} could not be loaded")
        items.append(_case_snapshot(case, loan, rules))
        if case.branch_id:
            branch_ids.add(case.branch_id)

    now = datetime.now(timezone.utc)
    reference = f"LDC-{now:%Y%m%d}-{uuid4().hex[:8].upper()}"
    total = sum((Decimal(str(item["outstanding_balance"])) for item in items), Decimal("0"))
    company = context.company
    row = CompanyOperatingRecord(
        company_id=context.company_id,
        branch_id=next(iter(branch_ids)) if len(branch_ids) == 1 else None,
        module=RECORD_MODULE,
        record_type=RECORD_TYPE,
        reference=reference,
        title=f"Lelefa collection referral · {len(items)} account{'s' if len(items) != 1 else ''}",
        description=payload.note,
        status="submitted",
        priority="high",
        created_by_user_id=context.user.id,
        counterparty_name="Lelefa Debt Collectors",
        amount=total,
        currency="LSL",
        data={
            "schema_version": "1.1",
            "submitted_at": now.isoformat(),
            "submitted_by_user_id": str(context.user.id),
            "company": {
                "company_id": str(company.id),
                "name": company.name,
                "legal_name": company.legal_name,
                "registration_number": company.registration_number,
            },
            "criteria": rules,
            "items": items,
            "note": payload.note,
            "bridge_token": new_bridge_token(),
            "delivery": delivery_state("queued"),
            "offer": None,
            "decision": None,
        },
        tags=["lelefa", "external_collections", "referral", "ithute_internal"],
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    await _deliver_referral(db, row, context)
    db.refresh(row)
    return _record_payload(row)


@router.post("/referrals/{referral_id}/retry")
async def retry_lelefa_referral(
    referral_id: UUID,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(context, COLLECTIONS_ROLES)
    row = (
        db.query(CompanyOperatingRecord)
        .filter(
            CompanyOperatingRecord.id == referral_id,
            CompanyOperatingRecord.company_id == context.company_id,
            CompanyOperatingRecord.record_type == RECORD_TYPE,
        )
        .one_or_none()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Lelefa referral not found")
    if row.branch_id:
        assert_branch_scope(context, row.branch_id)
    if row.status in {"accepted", "active", "rejected"}:
        raise HTTPException(status_code=409, detail="This referral is already in a terminal or active agreement state")
    row.status = "submitted"
    db.commit()
    await _deliver_referral(db, row, context)
    db.refresh(row)
    return _record_payload(row)


@router.post("/integrations/referrals/verify")
def verify_internal_referral(
    payload: LelefaReferralVerification,
    x_ithute_bridge_token: str | None = Header(default=None, alias=BRIDGE_TOKEN_HEADER),
    db: Session = Depends(get_db),
):
    row = (
        db.query(CompanyOperatingRecord)
        .filter(
            CompanyOperatingRecord.id == payload.referral_id,
            CompanyOperatingRecord.reference == payload.referral_reference,
            CompanyOperatingRecord.company_id == payload.company_id,
            CompanyOperatingRecord.record_type == RECORD_TYPE,
            CompanyOperatingRecord.is_archived.is_(False),
        )
        .one_or_none()
    )
    if row is None or not bridge_token_matches(_stored_bridge_token(row), x_ithute_bridge_token):
        raise HTTPException(status_code=401, detail="The Ithute referral could not be verified")
    return {
        "verified": True,
        "referral_id": str(row.id),
        "referral_reference": row.reference,
        "company_id": str(row.company_id),
    }


@router.post("/integrations/offers")
def receive_lelefa_offer(
    payload: LelefaOfferCallback,
    x_ithute_bridge_token: str | None = Header(default=None, alias=BRIDGE_TOKEN_HEADER),
    x_idempotency_key: str | None = Header(default=None, alias=IDEMPOTENCY_HEADER),
    db: Session = Depends(get_db),
):
    row = (
        db.query(CompanyOperatingRecord)
        .filter(
            CompanyOperatingRecord.reference == payload.referral_reference,
            CompanyOperatingRecord.record_type == RECORD_TYPE,
        )
        .one_or_none()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="LoanHub referral not found")
    if not bridge_token_matches(_stored_bridge_token(row), x_ithute_bridge_token):
        raise HTTPException(status_code=401, detail="The Ithute bridge token is invalid")
    data = dict(row.data or {})
    existing_offer = data.get("offer") or {}
    if existing_offer.get("offer_id") == payload.offer.offer_id:
        return {"status": "already_received", "referral_id": str(row.id), "idempotency_key": x_idempotency_key}
    data["remote_referral_id"] = payload.remote_referral_id or data.get("remote_referral_id")
    data["offer"] = payload.offer.model_dump(mode="json")
    data["offer_received_at"] = datetime.now(timezone.utc).isoformat()
    row.data = data
    row.status = "offer_received"
    db.commit()
    return {"status": "offer_received", "referral_id": str(row.id), "reference": row.reference}


@router.post("/referrals/{referral_id}/offer/decision")
async def decide_lelefa_offer(
    referral_id: UUID,
    payload: LelefaOfferDecision,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(context, COMPANY_MANAGEMENT_ROLES)
    row = (
        db.query(CompanyOperatingRecord)
        .filter(
            CompanyOperatingRecord.id == referral_id,
            CompanyOperatingRecord.company_id == context.company_id,
            CompanyOperatingRecord.record_type == RECORD_TYPE,
        )
        .one_or_none()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Lelefa referral not found")
    data = dict(row.data or {})
    offer = data.get("offer") or {}
    offer_id = str(offer.get("offer_id") or "")
    if not offer_id:
        raise HTTPException(status_code=409, detail="Lelefa has not sent an offer for this referral yet")
    existing = data.get("decision") or {}
    if existing.get("status") == "delivered":
        raise HTTPException(status_code=409, detail="This Lelefa offer has already been decided")
    bridge_token = str(data.get("bridge_token") or "")
    if not bridge_token:
        bridge_token = new_bridge_token()
        data["bridge_token"] = bridge_token
        row.data = data
        db.commit()
        await _deliver_referral(db, row, context)
        db.refresh(row)
        data = dict(row.data or {})

    decision_payload = {
        "referral_reference": row.reference,
        "loanHub_referral_id": str(row.id),
        "company_id": str(context.company_id),
        "decision": payload.decision,
        "notes": payload.notes,
        "decided_by_user_id": str(context.user.id),
        "decided_at": datetime.now(timezone.utc).isoformat(),
    }
    data["decision"] = {**decision_payload, "status": "queued"}
    row.status = "acceptance_pending" if payload.decision == "accept" else "rejection_pending"
    row.data = data
    db.commit()
    try:
        remote = await post_to_lelefa(
            f"/api/v1/integrations/loanhub/offers/{offer_id}/decision",
            decision_payload,
            bridge_token=bridge_token,
            idempotency_key=f"loanhub-offer-decision:{row.id}:{payload.decision}",
        )
        data = dict(row.data or {})
        data["decision"] = {**decision_payload, "status": "delivered", "remote": remote}
        row.data = data
        row.status = "active" if payload.decision == "accept" else "rejected"
    except Exception as exc:
        data = dict(row.data or {})
        data["decision"] = {**decision_payload, "status": "failed", "message": str(exc)[:500]}
        row.data = data
    db.commit()
    db.refresh(row)
    return _record_payload(row)
