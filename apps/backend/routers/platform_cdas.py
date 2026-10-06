from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from core.access_control import require_platform_owner
from database.models.company import LoanCompany
from database.models.platform_cdas import PlatformCdasCredentialProfile, PlatformCdasSubscription, PlatformCdasTransaction
from database.models.user import User
from database.session import get_db
from integrations.cdas import CdasError
from integrations.cdas_compatible import CdasCompatibleClient as CdasClient
from services.cdas_request_budget import consume_cdas_request_budget
from services.platform_cdas_service import (
    decrypt_profile_password,
    get_profile,
    create_invoice,
    invoice_payload,
    list_invoices,
    list_transactions,
    mark_invoice_paid,
    profile_payload,
    refund_transaction,
    review_subscription,
    subscription_payload,
    transaction_payload,
    upsert_profile,
    waive_transaction,
)


router = APIRouter(prefix="/platform-owner/cdas", tags=["Platform Owner CDAS"])


class CdasProfileWrite(BaseModel):
    base_url: str = Field(min_length=8, max_length=500)
    username: str = Field(min_length=1, max_length=200)
    item_code: str | None = Field(default=None, max_length=100)
    password: str | None = Field(default=None, max_length=500)
    timeout_seconds: float = Field(default=20, ge=1, le=120)


class CdasTransactionWaiver(BaseModel):
    reason: str = Field(min_length=3, max_length=1000)


class CdasInvoiceCreate(BaseModel):
    period_start: date
    period_end: date


class ProviderInvoiceSettlement(BaseModel):
    payment_method: str = Field(pattern="^(cash|bank|electronic)$")
    proof_reference: str | None = Field(default=None, max_length=180)
    notes: str | None = Field(default=None, max_length=1000)


class CdasTransactionRefund(BaseModel):
    reason: str = Field(min_length=3, max_length=1000)
    payment_method: str = Field(pattern="^(cash|bank|electronic)$")
    proof_reference: str | None = Field(default=None, max_length=180)


class CdasSubscriptionDecision(BaseModel):
    decision: Literal["approved", "rejected", "suspended"]
    currency: str = Field(default="LSL", min_length=3, max_length=3)
    pricing: dict[str, float] = Field(default_factory=dict)
    credit_limit: float | None = Field(default=None, ge=0)
    warning_threshold: float | None = Field(default=None, ge=0)
    auto_suspend_on_limit: bool = True
    billing_due_days: int = Field(default=14, ge=1, le=90)
    reason: str | None = Field(default=None, max_length=1000)
    notes: str | None = Field(default=None, max_length=2000)


@router.get("/subscriptions")
def list_cdas_subscriptions(
    db: Session = Depends(get_db),
    _: User = Depends(require_platform_owner),
):
    rows = (
        db.query(PlatformCdasSubscription, LoanCompany)
        .join(LoanCompany, LoanCompany.id == PlatformCdasSubscription.company_id)
        .order_by(PlatformCdasSubscription.requested_at.desc())
        .all()
    )
    result = []
    for subscription, company in rows:
        item = subscription_payload(subscription, db=db)
        item["company"] = {
            "id": str(company.id),
            "name": company.name,
            "registration_number": company.registration_number,
            "license_number": company.license_number,
        }
        item["profiles"] = {
            environment: profile_payload(get_profile(db, company_id=company.id, environment=environment))
            for environment in ("test", "live")
        }
        result.append(item)
    return result


@router.post("/subscriptions/{company_id}/decision")
def decide_cdas_subscription(
    company_id: UUID,
    payload: CdasSubscriptionDecision,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_platform_owner),
):
    if payload.decision == "approved":
        profiles = [
            get_profile(db, company_id=company_id, environment="test"),
            get_profile(db, company_id=company_id, environment="live"),
        ]
        if not any(profile and profile.encrypted_password for profile in profiles):
            raise HTTPException(
                status_code=409,
                detail="Configure at least one company-specific CDAS credential profile before approval",
            )
    row = review_subscription(
        db,
        company_id=company_id,
        reviewer_user_id=current_user.id,
        decision=payload.decision,
        pricing=payload.pricing,
        currency=payload.currency,
        credit_limit=Decimal(str(payload.credit_limit)) if payload.credit_limit is not None else None,
        warning_threshold=Decimal(str(payload.warning_threshold)) if payload.warning_threshold is not None else None,
        auto_suspend_on_limit=payload.auto_suspend_on_limit,
        billing_due_days=payload.billing_due_days,
        reason=payload.reason,
        notes=payload.notes,
    )
    return subscription_payload(row, db=db)


@router.put("/companies/{company_id}/profiles/{environment}")
def put_cdas_profile(
    company_id: UUID,
    environment: Literal["test", "live"],
    payload: CdasProfileWrite,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_platform_owner),
):
    company = db.get(LoanCompany, company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Loan company not found")
    row = upsert_profile(
        db,
        company_id=company_id,
        environment=environment,
        base_url=payload.base_url,
        username=payload.username,
        item_code=payload.item_code,
        password=payload.password,
        timeout_seconds=payload.timeout_seconds,
        configured_by_user_id=current_user.id,
    )
    return profile_payload(row)


@router.post("/companies/{company_id}/profiles/{environment}/test")
async def test_cdas_profile(
    company_id: UUID,
    environment: Literal["test", "live"],
    db: Session = Depends(get_db),
    _: User = Depends(require_platform_owner),
):
    profile = get_profile(db, company_id=company_id, environment=environment)
    if not profile:
        raise HTTPException(status_code=404, detail="CDAS credential profile not found")
    password = decrypt_profile_password(profile)
    client = CdasClient(
        base_url=profile.base_url,
        username=profile.username,
        password=password,
        timeout_seconds=float(profile.timeout_seconds or 20),
        request_guard=lambda: consume_cdas_request_budget(company_id, environment),
    )
    from datetime import datetime, timezone
    try:
        await client.check_connection()
    except CdasError as exc:
        profile.last_test_status = "failed"
        profile.last_tested_at = datetime.now(timezone.utc)
        db.commit()
        raise HTTPException(status_code=502, detail=exc.message) from exc
    profile.last_test_status = "connected"
    profile.last_tested_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(profile)
    return profile_payload(profile)


@router.get("/transactions")
def get_cdas_transactions(
    db: Session = Depends(get_db),
    _: User = Depends(require_platform_owner),
    company_id: UUID | None = None,
    limit: int = 200,
):
    return list_transactions(db, company_id=company_id, limit=limit)



@router.post("/transactions/{transaction_id}/waive")
def waive_cdas_transaction(
    transaction_id: UUID,
    payload: CdasTransactionWaiver,
    db: Session = Depends(get_db),
    _: User = Depends(require_platform_owner),
):
    return transaction_payload(
        waive_transaction(db, transaction_id=transaction_id, reason=payload.reason)
    )


@router.post("/invoices/{company_id}")
def issue_cdas_invoice(
    company_id: UUID,
    payload: CdasInvoiceCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_platform_owner),
):
    return invoice_payload(
        create_invoice(
            db,
            company_id=company_id,
            period_start=payload.period_start,
            period_end=payload.period_end,
        )
    )


@router.get("/invoices")
def get_cdas_invoices(
    db: Session = Depends(get_db),
    _: User = Depends(require_platform_owner),
    company_id: UUID | None = None,
    limit: int = 200,
):
    return list_invoices(db, company_id=company_id, limit=limit)


@router.post("/invoices/{invoice_id}/paid")
def mark_cdas_invoice_paid(
    invoice_id: UUID,
    payload: ProviderInvoiceSettlement,
    db: Session = Depends(get_db),
    _: User = Depends(require_platform_owner),
):
    return invoice_payload(mark_invoice_paid(
        db,
        invoice_id=invoice_id,
        payment_method=payload.payment_method,
        proof_reference=payload.proof_reference,
        notes=payload.notes,
    ))



@router.post("/transactions/{transaction_id}/refund")
def refund_cdas_transaction(
    transaction_id: UUID,
    payload: CdasTransactionRefund,
    db: Session = Depends(get_db),
    _: User = Depends(require_platform_owner),
):
    return transaction_payload(
        refund_transaction(
            db,
            transaction_id=transaction_id,
            reason=payload.reason,
            payment_method=payload.payment_method,
            proof_reference=payload.proof_reference,
        )
    )
