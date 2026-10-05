from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal, InvalidOperation
from uuid import UUID, uuid4

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from database.models.company_staff import CompanyStaff
from database.models.enums import NotificationType, UserRole
from database.models.notification import Notification
from database.models.origination import OriginationIntegrationConfiguration
from database.models.platform_credit_bureau import (
    PlatformCreditBureauConfiguration,
    PlatformCreditBureauInvoice,
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


def outstanding_balance(db: Session, *, company_id: UUID) -> Decimal:
    value = (
        db.query(func.coalesce(func.sum(PlatformCreditBureauTransaction.amount), 0))
        .filter(
            PlatformCreditBureauTransaction.company_id == company_id,
            PlatformCreditBureauTransaction.provider == "experian",
            PlatformCreditBureauTransaction.status.in_(("reserved", "accrued", "invoiced")),
        )
        .scalar()
        or Decimal("0")
    )
    return _money(value)


def month_usage(db: Session, *, company_id: UUID, now: datetime | None = None) -> tuple[int, Decimal]:
    now = now or datetime.now(timezone.utc)
    start = datetime(now.year, now.month, 1, tzinfo=timezone.utc)
    if now.month == 12:
        end = datetime(now.year + 1, 1, 1, tzinfo=timezone.utc)
    else:
        end = datetime(now.year, now.month + 1, 1, tzinfo=timezone.utc)
    count, amount = (
        db.query(
            func.count(PlatformCreditBureauTransaction.id),
            func.coalesce(func.sum(PlatformCreditBureauTransaction.amount), 0),
        )
        .filter(
            PlatformCreditBureauTransaction.company_id == company_id,
            PlatformCreditBureauTransaction.provider == "experian",
            PlatformCreditBureauTransaction.accrued_at >= start,
            PlatformCreditBureauTransaction.accrued_at < end,
            PlatformCreditBureauTransaction.status.notin_(("waived", "cancelled", "reserved")),
        )
        .one()
    )
    return int(count or 0), _money(amount)


def usage_summary(db: Session, *, company_id: UUID) -> dict:
    subscription = get_subscription(db, company_id=company_id)
    count, month_amount = month_usage(db, company_id=company_id)
    outstanding = outstanding_balance(db, company_id=company_id)
    credit_limit = _money(subscription.credit_limit) if subscription and subscription.credit_limit is not None else None
    remaining = max(Decimal("0"), credit_limit - outstanding) if credit_limit is not None else None
    return {
        "status": subscription.status if subscription else "not_subscribed",
        "currency": subscription.currency if subscription else DEFAULT_CURRENCY,
        "price_per_live_transaction": float(subscription.price_per_transaction or 0) if subscription else None,
        "sandbox_price": 0.0,
        "month_transaction_count": count,
        "month_amount": float(month_amount),
        "outstanding_balance": float(outstanding),
        "credit_limit": float(credit_limit) if credit_limit is not None else None,
        "remaining_credit": float(remaining) if remaining is not None else None,
        "warning_threshold": float(subscription.warning_threshold) if subscription and subscription.warning_threshold is not None else None,
        "auto_suspend_on_limit": bool(subscription.auto_suspend_on_limit) if subscription else False,
        "billing_due_days": int(subscription.billing_due_days or 14) if subscription else 14,
    }


def subscription_payload(row: PlatformCreditBureauSubscription | None, db: Session | None = None) -> dict:
    if not row:
        return {
            "provider": "experian",
            "status": "not_subscribed",
            "approved": False,
            "price_per_transaction": None,
            "currency": DEFAULT_CURRENCY,
            "credit_limit": None,
            "warning_threshold": None,
            "auto_suspend_on_limit": True,
            "billing_due_days": 14,
            "requested_at": None,
            "reviewed_at": None,
            "approved_at": None,
            "suspended_at": None,
            "rejection_reason": None,
        }
    payload = {
        "id": str(row.id),
        "provider": row.provider,
        "company_id": str(row.company_id),
        "status": row.status,
        "approved": row.status == "approved",
        "price_per_transaction": float(row.price_per_transaction or 0),
        "currency": row.currency,
        "credit_limit": float(row.credit_limit) if row.credit_limit is not None else None,
        "warning_threshold": float(row.warning_threshold) if row.warning_threshold is not None else None,
        "auto_suspend_on_limit": bool(row.auto_suspend_on_limit),
        "billing_due_days": int(row.billing_due_days or 14),
        "requested_at": row.requested_at,
        "reviewed_at": row.reviewed_at,
        "approved_at": row.approved_at,
        "suspended_at": row.suspended_at,
        "rejection_reason": row.rejection_reason,
        "notes": row.notes,
    }
    if db is not None:
        payload["usage"] = usage_summary(db, company_id=row.company_id)
    return payload


def _notify_company_owners(
    db: Session,
    *,
    company_id: UUID,
    title: str,
    message: str,
    event_type: str,
    entity_type: str = "credit_bureau_subscription",
    entity_id: str | None = None,
    priority: str = "normal",
    deduplication_key: str | None = None,
) -> None:
    owners = (
        db.query(CompanyStaff)
        .filter(
            CompanyStaff.company_id == company_id,
            CompanyStaff.role == UserRole.COMPANY_OWNER,
            CompanyStaff.is_active.is_(True),
        )
        .all()
    )
    for owner in owners:
        if deduplication_key:
            existing = (
                db.query(Notification)
                .filter(
                    Notification.user_id == owner.user_id,
                    Notification.deduplication_key == f"{deduplication_key}:{owner.user_id}",
                )
                .first()
            )
            if existing:
                continue
        db.add(
            Notification(
                user_id=owner.user_id,
                company_id=company_id,
                title=title,
                message=message,
                notification_type=NotificationType.SYSTEM,
                event_type=event_type,
                action="view",
                entity_type=entity_type,
                entity_id=entity_id,
                action_url="/company/origination/experian",
                icon="credit-card",
                priority=priority,
                data={"provider": "experian"},
                deduplication_key=f"{deduplication_key}:{owner.user_id}" if deduplication_key else None,
            )
        )


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
    credit_limit: Decimal | None = None,
    warning_threshold: Decimal | None = None,
    auto_suspend_on_limit: bool | None = None,
    billing_due_days: int | None = None,
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
    if credit_limit is not None:
        normalized_limit = _money(credit_limit)
        row.credit_limit = normalized_limit if normalized_limit > 0 else None
    if warning_threshold is not None:
        normalized_warning = _money(warning_threshold)
        row.warning_threshold = normalized_warning if normalized_warning > 0 else None
    if auto_suspend_on_limit is not None:
        row.auto_suspend_on_limit = bool(auto_suspend_on_limit)
    if billing_due_days is not None:
        row.billing_due_days = max(1, min(int(billing_due_days), 90))
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

    _notify_company_owners(
        db,
        company_id=company_id,
        title=f"Credit Bureau subscription {normalized}",
        message=(
            f"Your Credit Bureau subscription is now {normalized}. "
            f"Live enquiries cost {row.currency} {_money(row.price_per_transaction):.2f} each."
            if normalized == "approved"
            else f"Your Credit Bureau subscription is now {normalized}."
        ),
        event_type=f"credit_bureau.subscription.{normalized}",
        entity_id=str(row.id),
        priority="high" if normalized in {"rejected", "suspended"} else "normal",
    )
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
        raise HTTPException(status_code=402, detail="This lending company has not subscribed to the LoanHub Credit Bureau service.")
    if row.status == "pending":
        raise HTTPException(status_code=403, detail="Credit Bureau subscription is awaiting Platform Owner approval.")
    if row.status != "approved":
        raise HTTPException(status_code=403, detail=f"Credit Bureau subscription is {row.status}. Contact the LoanHub Platform Owner.")
    return row


def assert_live_credit_available(
    db: Session,
    *,
    subscription: PlatformCreditBureauSubscription,
    environment: str,
) -> None:
    if str(environment).lower() != "live":
        return
    if subscription.credit_limit is None:
        return
    outstanding = outstanding_balance(db, company_id=subscription.company_id)
    price = _money(subscription.price_per_transaction)
    limit = _money(subscription.credit_limit)
    if outstanding + price <= limit:
        return
    if subscription.auto_suspend_on_limit:
        subscription.status = "suspended"
        subscription.suspended_at = datetime.now(timezone.utc)
        _notify_company_owners(
            db,
            company_id=subscription.company_id,
            title="Credit Bureau access automatically suspended",
            message=(
                f"Live Credit Bureau usage reached the approved credit limit of "
                f"{subscription.currency} {limit:.2f}. Settle the outstanding balance or contact the Platform Owner."
            ),
            event_type="credit_bureau.credit_limit.suspended",
            entity_id=str(subscription.id),
            priority="high",
            deduplication_key=f"credit-bureau-limit-{subscription.id}-{limit}",
        )
        db.commit()
    raise HTTPException(
        status_code=402,
        detail=(
            f"Credit Bureau credit limit reached. Outstanding {subscription.currency} {outstanding:.2f}; "
            f"next Live enquiry {subscription.currency} {price:.2f}; limit {subscription.currency} {limit:.2f}."
        ),
    )


def reserve_enquiry_charge(
    db: Session,
    *,
    subscription: PlatformCreditBureauSubscription,
    enquiry_id: UUID,
    environment: str,
) -> PlatformCreditBureauTransaction | None:
    """Atomically reserve Live PAYG credit before contacting the bureau.

    Reservations are not billable. They only prevent concurrent successful
    enquiries from overshooting the company's approved credit limit.
    """
    if str(environment).strip().lower() != "live":
        return None

    existing = (
        db.query(PlatformCreditBureauTransaction)
        .filter(PlatformCreditBureauTransaction.enquiry_id == enquiry_id)
        .first()
    )
    if existing:
        return existing

    locked = (
        db.query(PlatformCreditBureauSubscription)
        .filter(
            PlatformCreditBureauSubscription.id == subscription.id,
            PlatformCreditBureauSubscription.provider == "experian",
        )
        .with_for_update()
        .one()
    )
    if locked.status != "approved":
        raise HTTPException(
            status_code=403,
            detail=f"Credit Bureau subscription is {locked.status}. Contact the LoanHub Platform Owner.",
        )

    price = _money(locked.price_per_transaction)
    if locked.credit_limit is not None:
        outstanding = outstanding_balance(db, company_id=locked.company_id)
        limit = _money(locked.credit_limit)
        if outstanding + price > limit:
            if locked.auto_suspend_on_limit:
                locked.status = "suspended"
                locked.suspended_at = datetime.now(timezone.utc)
                _notify_company_owners(
                    db,
                    company_id=locked.company_id,
                    title="Credit Bureau access automatically suspended",
                    message=(
                        f"Live Credit Bureau usage reached the approved credit limit of "
                        f"{locked.currency} {limit:.2f}. Settle the outstanding balance or contact the Platform Owner."
                    ),
                    event_type="credit_bureau.credit_limit.suspended",
                    entity_id=str(locked.id),
                    priority="high",
                    deduplication_key=f"credit-bureau-limit-{locked.id}-{limit}",
                )
                db.commit()
            raise HTTPException(
                status_code=402,
                detail=(
                    f"Credit Bureau credit limit reached. Outstanding {locked.currency} {outstanding:.2f}; "
                    f"next Live enquiry {locked.currency} {price:.2f}; limit {locked.currency} {limit:.2f}."
                ),
            )

    now = datetime.now(timezone.utc)
    transaction = PlatformCreditBureauTransaction(
        provider="experian",
        company_id=locked.company_id,
        subscription_id=locked.id,
        enquiry_id=enquiry_id,
        transaction_reference=f"CB-{uuid4().hex[:24].upper()}",
        unit_price=price,
        amount=price,
        currency=locked.currency or DEFAULT_CURRENCY,
        status="reserved",
        accrued_at=now,
        metadata_json={
            "billing_model": "pay_as_you_go",
            "charge_trigger": "successful_fresh_provider_enquiry",
            "environment": "live",
            "price_snapshot": float(price),
            "reservation": {
                "state": "reserved",
                "reserved_at": now.isoformat(),
            },
        },
    )
    db.add(transaction)
    db.commit()
    db.refresh(transaction)
    return transaction


def cancel_enquiry_reservation(
    db: Session,
    *,
    enquiry_id: UUID,
    reason: str,
) -> PlatformCreditBureauTransaction | None:
    row = (
        db.query(PlatformCreditBureauTransaction)
        .filter(
            PlatformCreditBureauTransaction.enquiry_id == enquiry_id,
            PlatformCreditBureauTransaction.status == "reserved",
        )
        .first()
    )
    if not row:
        return None
    metadata = dict(row.metadata_json or {})
    reservation = dict(metadata.get("reservation") or {})
    reservation.update(
        {
            "state": "cancelled",
            "cancelled_at": datetime.now(timezone.utc).isoformat(),
            "reason": str(reason or "provider_request_failed")[:500],
        }
    )
    metadata["reservation"] = reservation
    row.metadata_json = metadata
    row.status = "cancelled"
    db.commit()
    db.refresh(row)
    return row


def reconcile_payg_reservations(
    db: Session,
    *,
    now: datetime | None = None,
    stale_after_minutes: int = 60,
) -> dict[str, int]:
    """Self-heal reservations left behind by process crashes or interrupted calls."""
    from database.models.lending_operations import CreditBureauEnquiry

    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(minutes=max(5, int(stale_after_minutes)))
    rows = (
        db.query(PlatformCreditBureauTransaction, CreditBureauEnquiry)
        .join(CreditBureauEnquiry, CreditBureauEnquiry.id == PlatformCreditBureauTransaction.enquiry_id)
        .filter(
            PlatformCreditBureauTransaction.provider == "experian",
            PlatformCreditBureauTransaction.status == "reserved",
            PlatformCreditBureauTransaction.accrued_at <= cutoff,
        )
        .all()
    )
    finalized = 0
    cancelled = 0
    for transaction, enquiry in rows:
        metadata = dict(transaction.metadata_json or {})
        reservation = dict(metadata.get("reservation") or {})
        if enquiry.status == "completed":
            transaction.status = "accrued"
            reservation.update(
                {
                    "state": "finalized",
                    "finalized_at": now.isoformat(),
                    "reconciled": True,
                }
            )
            finalized += 1
        else:
            transaction.status = "cancelled"
            reservation.update(
                {
                    "state": "cancelled",
                    "cancelled_at": now.isoformat(),
                    "reason": (
                        "enquiry_failed"
                        if enquiry.status == "failed"
                        else "stale_reservation_timeout"
                    ),
                    "reconciled": True,
                }
            )
            cancelled += 1
        metadata["reservation"] = reservation
        transaction.metadata_json = metadata

    if finalized or cancelled:
        db.commit()
    return {"finalized": finalized, "cancelled": cancelled}


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
    is_live = str(environment).strip().lower() == "live"
    if existing:
        if is_live and existing.status == "reserved":
            metadata = dict(existing.metadata_json or {})
            reservation = dict(metadata.get("reservation") or {})
            reservation.update({
                "state": "finalized",
                "finalized_at": datetime.now(timezone.utc).isoformat(),
            })
            metadata["reservation"] = reservation
            existing.metadata_json = metadata
            existing.status = "accrued"
            db.flush()
        return existing

    price = _money(subscription.price_per_transaction) if is_live else Decimal("0.00")
    transaction = PlatformCreditBureauTransaction(
        provider="experian",
        company_id=subscription.company_id,
        subscription_id=subscription.id,
        enquiry_id=enquiry_id,
        transaction_reference=f"CB-{uuid4().hex[:24].upper()}",
        unit_price=price,
        amount=price,
        currency=subscription.currency or DEFAULT_CURRENCY,
        status="accrued" if is_live else "sandbox",
        accrued_at=datetime.now(timezone.utc),
        metadata_json={
            "billing_model": "pay_as_you_go",
            "charge_trigger": "successful_fresh_provider_enquiry" if is_live else "sandbox_free",
            "environment": environment,
            "price_snapshot": float(price),
        },
    )
    db.add(transaction)
    db.flush()
    if is_live and price > 0:
        from services.accounting_service import record_credit_bureau_transaction_accrual
        record_credit_bureau_transaction_accrual(db, transaction)

    if is_live and subscription.warning_threshold is not None:
        projected = outstanding_balance(db, company_id=subscription.company_id)
        threshold = _money(subscription.warning_threshold)
        if projected >= threshold:
            _notify_company_owners(
                db,
                company_id=subscription.company_id,
                title="Credit Bureau spending warning",
                message=(
                    f"Your outstanding Live Credit Bureau usage is now {subscription.currency} {projected:.2f}, "
                    f"which has reached the warning threshold of {subscription.currency} {threshold:.2f}."
                ),
                event_type="credit_bureau.credit_limit.warning",
                entity_id=str(subscription.id),
                priority="high",
                deduplication_key=f"credit-bureau-warning-{subscription.id}-{datetime.now(timezone.utc).strftime('%Y-%m')}",
            )
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


def waive_transaction(
    db: Session,
    *,
    transaction_id: UUID,
    reason: str,
) -> PlatformCreditBureauTransaction:
    row = (
        db.query(PlatformCreditBureauTransaction)
        .filter(PlatformCreditBureauTransaction.id == transaction_id)
        .with_for_update()
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Credit Bureau transaction not found")
    if row.status != "accrued":
        raise HTTPException(
            status_code=409,
            detail="Only an accrued, not-yet-invoiced Credit Bureau transaction can be waived",
        )
    row.status = "waived"
    row.waived_at = datetime.now(timezone.utc)
    row.waiver_reason = reason.strip()
    from services.accounting_service import reverse_credit_bureau_transaction_accrual
    reverse_credit_bureau_transaction_accrual(db, row)
    _notify_company_owners(
        db,
        company_id=row.company_id,
        title="Credit Bureau charge waived",
        message=f"Charge {row.transaction_reference} for {row.currency} {_money(row.amount):.2f} was waived.",
        event_type="credit_bureau.transaction.waived",
        entity_type="credit_bureau_transaction",
        entity_id=str(row.id),
    )
    db.commit()
    db.refresh(row)
    return row


def refund_transaction(
    db: Session,
    *,
    transaction_id: UUID,
    reason: str,
    payment_method: str,
    proof_reference: str | None,
) -> PlatformCreditBureauTransaction:
    row = db.query(PlatformCreditBureauTransaction).filter(
        PlatformCreditBureauTransaction.id == transaction_id
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="Credit Bureau transaction not found")
    if row.status == "refunded":
        return row
    if row.status != "settled":
        raise HTTPException(status_code=409, detail="Only a settled Credit Bureau transaction can be refunded")
    method = payment_method.strip().lower()
    if method not in {"cash", "bank", "electronic"}:
        raise HTTPException(status_code=422, detail="Unsupported refund payment method")
    if method != "cash" and not (proof_reference or "").strip():
        raise HTTPException(status_code=422, detail="Non-cash refunds require proof_reference")

    refunded_at = datetime.now(timezone.utc)
    metadata = dict(row.metadata_json or {})
    metadata["refund"] = {
        "payment_method": method,
        "proof_reference": (proof_reference or "").strip() or None,
        "reason": reason.strip(),
        "recorded_at": refunded_at.isoformat(),
    }
    row.metadata_json = metadata
    row.status = "refunded"

    from services.accounting_service import record_credit_bureau_transaction_refund
    record_credit_bureau_transaction_refund(db, row)
    _notify_company_owners(
        db,
        company_id=row.company_id,
        title="Credit Bureau charge refunded",
        message=f"Charge {row.transaction_reference} for {row.currency} {_money(row.amount):.2f} has been refunded.",
        event_type="credit_bureau.transaction.refunded",
        entity_type="credit_bureau_transaction",
        entity_id=str(row.id),
    )
    db.commit()
    db.refresh(row)
    return row


def create_invoice(
    db: Session,
    *,
    company_id: UUID,
    period_start: date,
    period_end: date,
) -> PlatformCreditBureauInvoice:
    if period_end < period_start:
        raise HTTPException(status_code=422, detail="Invoice period end cannot be before period start")
    existing = (
        db.query(PlatformCreditBureauInvoice)
        .filter(
            PlatformCreditBureauInvoice.company_id == company_id,
            PlatformCreditBureauInvoice.provider == "experian",
            PlatformCreditBureauInvoice.period_start == period_start,
            PlatformCreditBureauInvoice.period_end == period_end,
        )
        .first()
    )
    if existing:
        return existing
    subscription = get_subscription(db, company_id=company_id)
    if not subscription:
        raise HTTPException(status_code=404, detail="Credit Bureau subscription not found")

    start_dt = datetime.combine(period_start, time.min, tzinfo=timezone.utc)
    end_dt = datetime.combine(period_end + timedelta(days=1), time.min, tzinfo=timezone.utc)
    rows = (
        db.query(PlatformCreditBureauTransaction)
        .filter(
            PlatformCreditBureauTransaction.company_id == company_id,
            PlatformCreditBureauTransaction.provider == "experian",
            PlatformCreditBureauTransaction.accrued_at >= start_dt,
            PlatformCreditBureauTransaction.accrued_at < end_dt,
            PlatformCreditBureauTransaction.status.in_(("accrued", "waived")),
        )
        .order_by(PlatformCreditBureauTransaction.accrued_at.asc())
        .with_for_update()
        .all()
    )
    subtotal = sum((_money(row.amount) for row in rows), Decimal("0"))
    waived = sum((_money(row.amount) for row in rows if row.status == "waived"), Decimal("0"))
    due = subtotal - waived
    issued_at = datetime.now(timezone.utc)
    invoice = PlatformCreditBureauInvoice(
        provider="experian",
        company_id=company_id,
        subscription_id=subscription.id,
        invoice_number=f"CBI-{issued_at.strftime('%Y%m')}-{uuid4().hex[:10].upper()}",
        period_start=period_start,
        period_end=period_end,
        transaction_count=len(rows),
        subtotal=_money(subtotal),
        waived_amount=_money(waived),
        amount_due=_money(due),
        currency=subscription.currency,
        status="issued" if due > 0 else "paid",
        issued_at=issued_at,
        due_at=issued_at + timedelta(days=int(subscription.billing_due_days or 14)),
        paid_at=issued_at if due <= 0 else None,
        snapshot={
            "transaction_ids": [str(row.id) for row in rows],
            "pricing_is_snapshotted_per_transaction": True,
        },
    )
    db.add(invoice)
    db.flush()
    # Usage is accrued at the successful provider transaction; invoice
    # creation groups those already-recognised charges and must not duplicate
    # expense/revenue recognition.
    for row in rows:
        if row.status == "accrued":
            row.status = "invoiced"
    _notify_company_owners(
        db,
        company_id=company_id,
        title="Credit Bureau invoice issued",
        message=f"Invoice {invoice.invoice_number} totals {invoice.currency} {_money(invoice.amount_due):.2f}.",
        event_type="credit_bureau.invoice.issued",
        entity_type="credit_bureau_invoice",
        entity_id=str(invoice.id),
        priority="high" if due > 0 else "normal",
    )
    db.commit()
    db.refresh(invoice)
    return invoice


def invoice_payload(row: PlatformCreditBureauInvoice) -> dict:
    return {
        "id": str(row.id),
        "company_id": str(row.company_id),
        "subscription_id": str(row.subscription_id),
        "invoice_number": row.invoice_number,
        "period_start": row.period_start,
        "period_end": row.period_end,
        "transaction_count": int(row.transaction_count or 0),
        "subtotal": float(row.subtotal or 0),
        "waived_amount": float(row.waived_amount or 0),
        "amount_due": float(row.amount_due or 0),
        "currency": row.currency,
        "status": row.status,
        "issued_at": row.issued_at,
        "due_at": row.due_at,
        "paid_at": row.paid_at,
        "notes": row.notes,
        "snapshot": dict(row.snapshot or {}),
    }


def list_invoices(db: Session, *, company_id: UUID | None = None, limit: int = 100) -> list[dict]:
    query = db.query(PlatformCreditBureauInvoice)
    if company_id is not None:
        query = query.filter(PlatformCreditBureauInvoice.company_id == company_id)
    rows = query.order_by(PlatformCreditBureauInvoice.issued_at.desc()).limit(max(1, min(limit, 500))).all()
    return [invoice_payload(row) for row in rows]


def mark_invoice_paid(
    db: Session,
    *,
    invoice_id: UUID,
    payment_method: str,
    proof_reference: str | None,
    notes: str | None = None,
) -> PlatformCreditBureauInvoice:
    invoice = (
        db.query(PlatformCreditBureauInvoice)
        .filter(PlatformCreditBureauInvoice.id == invoice_id)
        .with_for_update()
        .first()
    )
    if not invoice:
        raise HTTPException(status_code=404, detail="Credit Bureau invoice not found")
    if invoice.status == "paid":
        return invoice
    method = payment_method.strip().lower()
    if method not in {"cash", "bank", "electronic"}:
        raise HTTPException(status_code=422, detail="Unsupported invoice payment method")
    if method != "cash" and not (proof_reference or "").strip():
        raise HTTPException(status_code=422, detail="Non-cash invoice payments require proof_reference")
    paid_at = datetime.now(timezone.utc)
    invoice.status = "paid"
    invoice.paid_at = paid_at
    snapshot = dict(invoice.snapshot or {})
    snapshot["settlement"] = {
        "payment_method": method,
        "proof_reference": (proof_reference or "").strip() or None,
        "notes": (notes or "").strip() or None,
        "recorded_at": paid_at.isoformat(),
    }
    invoice.snapshot = snapshot
    from services.accounting_service import record_credit_bureau_invoice_payment
    record_credit_bureau_invoice_payment(db, invoice)
    transaction_ids = [UUID(value) for value in dict(invoice.snapshot or {}).get("transaction_ids", [])]
    if transaction_ids:
        rows = (
            db.query(PlatformCreditBureauTransaction)
            .filter(
                PlatformCreditBureauTransaction.id.in_(transaction_ids),
                PlatformCreditBureauTransaction.status == "invoiced",
            )
            .order_by(PlatformCreditBureauTransaction.id.asc())
            .with_for_update()
            .all()
        )
        for row in rows:
            row.status = "settled"
            row.settled_at = paid_at

    subscription = get_subscription(db, company_id=invoice.company_id)
    if subscription and subscription.status == "suspended" and subscription.auto_suspend_on_limit:
        if subscription.credit_limit is None or outstanding_balance(db, company_id=invoice.company_id) < _money(subscription.credit_limit):
            subscription.status = "approved"
            subscription.suspended_at = None

    _notify_company_owners(
        db,
        company_id=invoice.company_id,
        title="Credit Bureau invoice paid",
        message=f"Invoice {invoice.invoice_number} has been marked paid.",
        event_type="credit_bureau.invoice.paid",
        entity_type="credit_bureau_invoice",
        entity_id=str(invoice.id),
    )
    db.commit()
    db.refresh(invoice)
    return invoice


def run_monthly_invoice_cycle(db: Session, *, now: datetime | None = None) -> int:
    """Issue the previous calendar month's invoices once; safe to run repeatedly."""
    now = now or datetime.now(timezone.utc)
    first_this_month = date(now.year, now.month, 1)
    previous_end = first_this_month - timedelta(days=1)
    previous_start = date(previous_end.year, previous_end.month, 1)
    subscriptions = (
        db.query(PlatformCreditBureauSubscription)
        .filter(
            PlatformCreditBureauSubscription.provider == "experian",
            PlatformCreditBureauSubscription.status.in_(("approved", "suspended")),
        )
        .all()
    )
    issued = 0
    for subscription in subscriptions:
        existing = (
            db.query(PlatformCreditBureauInvoice)
            .filter(
                PlatformCreditBureauInvoice.company_id == subscription.company_id,
                PlatformCreditBureauInvoice.provider == "experian",
                PlatformCreditBureauInvoice.period_start == previous_start,
                PlatformCreditBureauInvoice.period_end == previous_end,
            )
            .first()
        )
        if existing:
            continue
        live_count = (
            db.query(func.count(PlatformCreditBureauTransaction.id))
            .filter(
                PlatformCreditBureauTransaction.company_id == subscription.company_id,
                PlatformCreditBureauTransaction.provider == "experian",
                PlatformCreditBureauTransaction.accrued_at >= datetime.combine(previous_start, time.min, tzinfo=timezone.utc),
                PlatformCreditBureauTransaction.accrued_at < datetime.combine(first_this_month, time.min, tzinfo=timezone.utc),
                PlatformCreditBureauTransaction.status.in_(("accrued", "waived")),
            )
            .scalar()
            or 0
        )
        if not live_count:
            continue
        create_invoice(
            db,
            company_id=subscription.company_id,
            period_start=previous_start,
            period_end=previous_end,
        )
        issued += 1
    return issued


def suspend_overdue_accounts(db: Session, *, now: datetime | None = None) -> int:
    """Suspend approved PAYG access when an issued invoice is overdue."""
    now = now or datetime.now(timezone.utc)
    overdue_company_ids = {
        company_id
        for (company_id,) in (
            db.query(PlatformCreditBureauInvoice.company_id)
            .filter(
                PlatformCreditBureauInvoice.provider == "experian",
                PlatformCreditBureauInvoice.status == "issued",
                PlatformCreditBureauInvoice.amount_due > 0,
                PlatformCreditBureauInvoice.due_at < now,
            )
            .all()
        )
    }
    suspended = 0
    for company_id in overdue_company_ids:
        subscription = get_subscription(db, company_id=company_id)
        if not subscription or subscription.status != "approved" or not subscription.auto_suspend_on_limit:
            continue
        subscription.status = "suspended"
        subscription.suspended_at = now
        _notify_company_owners(
            db,
            company_id=company_id,
            title="Credit Bureau access suspended for overdue invoice",
            message="Live Credit Bureau access has been suspended because a PAYG invoice is overdue.",
            event_type="credit_bureau.invoice.overdue_suspension",
            entity_id=str(subscription.id),
            priority="high",
            deduplication_key=f"credit-bureau-overdue-{subscription.id}-{now.strftime('%Y-%m-%d')}",
        )
        suspended += 1
    if suspended:
        db.commit()
    return suspended
