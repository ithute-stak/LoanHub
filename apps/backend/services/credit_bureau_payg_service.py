from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from uuid import UUID, uuid4

from fastapi import HTTPException
from sqlalchemy.orm import Session

from database.models.origination import OriginationIntegrationConfiguration
from database.models.platform_credit_bureau import (
    PlatformCreditBureauConfiguration,
    PlatformCreditBureauSubscription,
    PlatformCreditBureauTransaction,
)


DEFAULT_PAYG_PRICE = Decimal("0.00")
DEFAULT_CURRENCY = "LSL"


def _money(value, *, default: Decimal = DEFAULT_PAYG_PRICE) -> Decimal:
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return default
    return amount.quantize(Decimal("0.01"))


def platform_default_pricing(db: Session) -> tuple[Decimal, str]:
    row = (
        db.query(PlatformCreditBureauConfiguration)
        .filter(PlatformCreditBureauConfiguration.provider == "experian")
        .first()
    )
    configuration = dict(row.configuration or {}) if row else {}
    price = _money(configuration.get("default_price_per_transaction"), default=DEFAULT_PAYG_PRICE)
    currency = str(configuration.get("billing_currency") or DEFAULT_CURRENCY).strip().upper()[:3] or DEFAULT_CURRENCY
    return price, currency


def get_subscription(db: Session, *, company_id: UUID) -> PlatformCreditBureauSubscription | None:
    return (
        db.query(PlatformCreditBureauSubscription)
        .filter(
            PlatformCreditBureauSubscription.provider == "experian",
            PlatformCreditBureauSubscription.company_id == company_id,
        )
        .first()
    )


def subscription_payload(row: PlatformCreditBureauSubscription | None) -> dict:
    if not row:
        return {
            "provider": "experian",
            "status": "not_subscribed",
            "approved": False,
            "price_per_transaction": None,
            "currency": DEFAULT_CURRENCY,
            "requested_at": None,
            "reviewed_at": None,
            "approved_at": None,
            "suspended_at": None,
            "rejection_reason": None,
        }
    return {
        "id": str(row.id),
        "provider": row.provider,
        "company_id": str(row.company_id),
        "status": row.status,
        "approved": row.status == "approved",
        "price_per_transaction": float(row.price_per_transaction or 0),
        "currency": row.currency,
        "requested_at": row.requested_at,
        "reviewed_at": row.reviewed_at,
        "approved_at": row.approved_at,
        "suspended_at": row.suspended_at,
        "rejection_reason": row.rejection_reason,
        "notes": row.notes,
    }


def request_subscription(
    db: Session,
    *,
    company_id: UUID,
    requested_by_user_id: UUID,
) -> PlatformCreditBureauSubscription:
    row = get_subscription(db, company_id=company_id)
    now = datetime.now(timezone.utc)
    price, currency = platform_default_pricing(db)
    if not row:
        row = PlatformCreditBureauSubscription(
            provider="experian",
            company_id=company_id,
            status="pending",
            price_per_transaction=price,
            currency=currency,
            requested_by_user_id=requested_by_user_id,
            requested_at=now,
        )
        db.add(row)
    elif row.status == "approved":
        return row
    else:
        row.status = "pending"
        row.requested_by_user_id = requested_by_user_id
        row.requested_at = now
        row.reviewed_by_user_id = None
        row.reviewed_at = None
        row.approved_at = None
        row.suspended_at = None
        row.rejection_reason = None
        if row.price_per_transaction is None:
            row.price_per_transaction = price
        if not row.currency:
            row.currency = currency
    db.commit()
    db.refresh(row)
    return row


def review_subscription(
    db: Session,
    *,
    company_id: UUID,
    reviewer_user_id: UUID,
    decision: str,
    price_per_transaction: Decimal | None = None,
    currency: str | None = None,
    reason: str | None = None,
    notes: str | None = None,
) -> PlatformCreditBureauSubscription:
    row = get_subscription(db, company_id=company_id)
    if not row:
        raise HTTPException(status_code=404, detail="Credit bureau subscription request not found")

    normalized = str(decision).strip().lower()
    if normalized not in {"approved", "rejected", "suspended"}:
        raise HTTPException(status_code=422, detail="Decision must be approved, rejected or suspended")

    now = datetime.now(timezone.utc)
    if price_per_transaction is not None:
        row.price_per_transaction = _money(price_per_transaction)
    if currency:
        row.currency = str(currency).strip().upper()[:3]
    row.status = normalized
    row.reviewed_by_user_id = reviewer_user_id
    row.reviewed_at = now
    row.rejection_reason = reason if normalized == "rejected" else None
    row.notes = notes
    row.approved_at = now if normalized == "approved" else row.approved_at
    row.suspended_at = now if normalized == "suspended" else None

    integration = (
        db.query(OriginationIntegrationConfiguration)
        .filter(
            OriginationIntegrationConfiguration.company_id == company_id,
            OriginationIntegrationConfiguration.provider == "experian",
        )
        .first()
    )
    if not integration:
        integration = OriginationIntegrationConfiguration(
            company_id=company_id,
            provider="experian",
            environment="sandbox",
            is_enabled=False,
            configuration={},
        )
        db.add(integration)
    integration.is_enabled = normalized == "approved"

    db.commit()
    db.refresh(row)
    return row


def require_approved_subscription(
    db: Session,
    *,
    company_id: UUID,
) -> PlatformCreditBureauSubscription:
    row = get_subscription(db, company_id=company_id)
    if not row:
        raise HTTPException(
            status_code=402,
            detail="This lending company has not subscribed to the LoanHub Credit Bureau service.",
        )
    if row.status == "pending":
        raise HTTPException(
            status_code=403,
            detail="Credit Bureau subscription is awaiting Platform Owner approval.",
        )
    if row.status != "approved":
        raise HTTPException(
            status_code=403,
            detail=f"Credit Bureau subscription is {row.status}. Contact the LoanHub Platform Owner.",
        )
    return row


def accrue_successful_enquiry(
    db: Session,
    *,
    subscription: PlatformCreditBureauSubscription,
    enquiry_id: UUID,
    environment: str,
) -> PlatformCreditBureauTransaction:
    existing = (
        db.query(PlatformCreditBureauTransaction)
        .filter(PlatformCreditBureauTransaction.enquiry_id == enquiry_id)
        .first()
    )
    if existing:
        return existing

    price = _money(subscription.price_per_transaction)
    transaction = PlatformCreditBureauTransaction(
        provider="experian",
        company_id=subscription.company_id,
        subscription_id=subscription.id,
        enquiry_id=enquiry_id,
        transaction_reference=f"CB-{uuid4().hex[:24].upper()}",
        unit_price=price,
        amount=price,
        currency=subscription.currency or DEFAULT_CURRENCY,
        status="accrued",
        accrued_at=datetime.now(timezone.utc),
        metadata_json={
            "billing_model": "pay_as_you_go",
            "charge_trigger": "successful_fresh_provider_enquiry",
            "environment": environment,
        },
    )
    db.add(transaction)
    db.flush()
    return transaction


def company_transactions(db: Session, *, company_id: UUID, limit: int = 100) -> list[dict]:
    rows = (
        db.query(PlatformCreditBureauTransaction)
        .filter(PlatformCreditBureauTransaction.company_id == company_id)
        .order_by(PlatformCreditBureauTransaction.accrued_at.desc())
        .limit(max(1, min(limit, 500)))
        .all()
    )
    return [transaction_payload(row) for row in rows]


def transaction_payload(row: PlatformCreditBureauTransaction) -> dict:
    return {
        "id": str(row.id),
        "provider": row.provider,
        "company_id": str(row.company_id),
        "subscription_id": str(row.subscription_id),
        "enquiry_id": str(row.enquiry_id),
        "transaction_reference": row.transaction_reference,
        "unit_price": float(row.unit_price or 0),
        "amount": float(row.amount or 0),
        "currency": row.currency,
        "status": row.status,
        "accrued_at": row.accrued_at,
        "settled_at": row.settled_at,
        "waived_at": row.waived_at,
        "waiver_reason": row.waiver_reason,
        "metadata": dict(row.metadata_json or {}),
    }
