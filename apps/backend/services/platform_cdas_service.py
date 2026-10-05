from __future__ import annotations

import json
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal, InvalidOperation
from urllib.parse import urlparse
from uuid import UUID, uuid4

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from database.models.company_staff import CompanyStaff
from database.models.enums import NotificationType, UserRole
from database.models.notification import Notification
from database.models.platform_cdas import (
    PlatformCdasCredentialProfile,
    PlatformCdasInvoice,
    PlatformCdasSubscription,
    PlatformCdasTransaction,
)
from services.crypto_service import decrypt_control_secret, encrypt_control_secret


CDAS_PASSWORD_PURPOSE = b"loanhub-cdas-password-v1"
DEFAULT_TEST_BASE_URL = "https://test-cdas-thirdpartyapi.sentraptt.com"
DEFAULT_OPERATION_PRICING = {
    "employee_verification": 0.0,
    "affordability": 0.0,
    "deduction_lookup": 0.0,
    "registration": 0.0,
    "lifecycle": 0.0,
    "modification": 0.0,
    "settlement": 0.0,
    "document": 0.0,
}
ALLOWED_ENVIRONMENTS = {"test", "live"}


def _money(value, default: Decimal = Decimal("0.00")) -> Decimal:
    try:
        return Decimal(str(value)).quantize(Decimal("0.01"))
    except (InvalidOperation, TypeError, ValueError):
        return default


def normalize_pricing(value: dict | None) -> dict[str, float]:
    raw = value if isinstance(value, dict) else {}
    result: dict[str, float] = {}
    for key, default in DEFAULT_OPERATION_PRICING.items():
        amount = _money(raw.get(key, default))
        result[key] = float(max(Decimal("0.00"), amount))
    return result


def get_subscription(db: Session, *, company_id: UUID) -> PlatformCdasSubscription | None:
    return (
        db.query(PlatformCdasSubscription)
        .filter(PlatformCdasSubscription.company_id == company_id)
        .one_or_none()
    )


def require_approved_subscription(db: Session, *, company_id: UUID) -> PlatformCdasSubscription:
    row = get_subscription(db, company_id=company_id)
    if not row:
        raise HTTPException(status_code=402, detail="This lending company has not subscribed to the LoanHub CDAS service.")
    if row.status == "pending":
        raise HTTPException(status_code=403, detail="CDAS subscription is awaiting Platform Owner approval.")
    if row.status != "approved":
        raise HTTPException(status_code=403, detail=f"CDAS subscription is {row.status}. Contact the LoanHub Platform Owner.")
    return row


def subscription_payload(row: PlatformCdasSubscription | None, db: Session | None = None) -> dict:
    if not row:
        return {
            "status": "not_subscribed",
            "approved": False,
            "currency": "LSL",
            "pricing": dict(DEFAULT_OPERATION_PRICING),
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
    result = {
        "id": str(row.id),
        "company_id": str(row.company_id),
        "status": row.status,
        "approved": row.status == "approved",
        "currency": row.currency,
        "pricing": normalize_pricing(row.pricing),
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
        result["usage"] = usage_summary(db, company_id=row.company_id)
    return result


def request_subscription(db: Session, *, company_id: UUID, requested_by_user_id: UUID) -> PlatformCdasSubscription:
    row = get_subscription(db, company_id=company_id)
    now = datetime.now(timezone.utc)
    if not row:
        row = PlatformCdasSubscription(
            company_id=company_id,
            status="pending",
            currency="LSL",
            pricing=dict(DEFAULT_OPERATION_PRICING),
            requested_by_user_id=requested_by_user_id,
            requested_at=now,
        )
        db.add(row)
    elif row.status != "approved":
        row.status = "pending"
        row.requested_by_user_id = requested_by_user_id
        row.requested_at = now
        row.reviewed_by_user_id = None
        row.reviewed_at = None
        row.approved_at = None
        row.suspended_at = None
        row.rejection_reason = None
    db.commit()
    db.refresh(row)
    return row


def review_subscription(
    db: Session,
    *,
    company_id: UUID,
    reviewer_user_id: UUID,
    decision: str,
    pricing: dict | None = None,
    currency: str | None = None,
    credit_limit: Decimal | None = None,
    warning_threshold: Decimal | None = None,
    auto_suspend_on_limit: bool | None = None,
    billing_due_days: int | None = None,
    reason: str | None = None,
    notes: str | None = None,
) -> PlatformCdasSubscription:
    row = get_subscription(db, company_id=company_id)
    if not row:
        raise HTTPException(status_code=404, detail="CDAS subscription request not found")
    normalized = decision.strip().lower()
    if normalized not in {"approved", "rejected", "suspended"}:
        raise HTTPException(status_code=422, detail="Decision must be approved, rejected or suspended")
    rates = normalize_pricing(pricing if pricing is not None else row.pricing)
    if normalized == "approved" and not any(Decimal(str(value)) > 0 for value in rates.values()):
        raise HTTPException(status_code=409, detail="Set at least one positive CDAS Live transaction price before approval")
    row.status = normalized
    row.pricing = rates
    if currency:
        row.currency = currency.strip().upper()[:3] or "LSL"
    if credit_limit is not None:
        limit = _money(credit_limit)
        row.credit_limit = limit if limit > 0 else None
    if warning_threshold is not None:
        threshold = _money(warning_threshold)
        row.warning_threshold = threshold if threshold > 0 else None
    if auto_suspend_on_limit is not None:
        row.auto_suspend_on_limit = bool(auto_suspend_on_limit)
    if billing_due_days is not None:
        row.billing_due_days = max(1, min(int(billing_due_days), 90))
    now = datetime.now(timezone.utc)
    row.reviewed_by_user_id = reviewer_user_id
    row.reviewed_at = now
    row.approved_at = now if normalized == "approved" else row.approved_at
    row.suspended_at = now if normalized == "suspended" else None
    row.rejection_reason = reason if normalized == "rejected" else None
    row.notes = notes
    _notify_company_owners(
        db,
        company_id=company_id,
        title=f"CDAS subscription {normalized}",
        message=(
            f"Your CDAS subscription is now {normalized}. Live operations use the Platform Owner pricing schedule."
            if normalized == "approved"
            else f"Your CDAS subscription is now {normalized}."
        ),
        event_type=f"cdas.subscription.{normalized}",
        entity_id=str(row.id),
        priority="high" if normalized in {"rejected", "suspended"} else "normal",
    )
    db.commit()
    db.refresh(row)
    return row


def _validate_profile(environment: str, base_url: str, username: str) -> tuple[str, str, str]:
    env = environment.strip().lower()
    if env not in ALLOWED_ENVIRONMENTS:
        raise HTTPException(status_code=422, detail="CDAS environment must be test or live")
    url = base_url.strip().rstrip("/")
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise HTTPException(status_code=422, detail="CDAS base URL must be a credential-free HTTPS URL")
    if env == "test" and url != DEFAULT_TEST_BASE_URL:
        raise HTTPException(status_code=422, detail=f"CDAS Test must use {DEFAULT_TEST_BASE_URL}")
    if env == "live" and (parsed.hostname or "").lower() == (urlparse(DEFAULT_TEST_BASE_URL).hostname or "").lower():
        raise HTTPException(status_code=422, detail="CDAS Live cannot use the CDAS test host")
    user = username.strip()
    if not user:
        raise HTTPException(status_code=422, detail="CDAS username is required")
    return env, url, user


def _encrypt_password(password: str) -> str:
    ciphertext, nonce, version = encrypt_control_secret(password, CDAS_PASSWORD_PURPOSE)
    return json.dumps({"ciphertext": ciphertext, "nonce": nonce, "version": version}, separators=(",", ":"), sort_keys=True)


def decrypt_profile_password(profile: PlatformCdasCredentialProfile) -> str:
    try:
        payload = json.loads(profile.encrypted_password)
        return decrypt_control_secret(
            str(payload["ciphertext"]),
            str(payload["nonce"]),
            str(payload["version"]),
            CDAS_PASSWORD_PURPOSE,
        )
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Stored CDAS credential could not be verified") from exc


def get_profile(db: Session, *, company_id: UUID, environment: str) -> PlatformCdasCredentialProfile | None:
    return (
        db.query(PlatformCdasCredentialProfile)
        .filter(
            PlatformCdasCredentialProfile.company_id == company_id,
            PlatformCdasCredentialProfile.environment == environment.strip().lower(),
        )
        .one_or_none()
    )


def upsert_profile(
    db: Session,
    *,
    company_id: UUID,
    environment: str,
    base_url: str,
    username: str,
    item_code: str | None,
    password: str | None,
    timeout_seconds: float,
    configured_by_user_id: UUID,
) -> PlatformCdasCredentialProfile:
    env, url, user = _validate_profile(environment, base_url, username)
    if not 1 <= float(timeout_seconds) <= 120:
        raise HTTPException(status_code=422, detail="CDAS timeout must be between 1 and 120 seconds")
    duplicate = (
        db.query(PlatformCdasCredentialProfile)
        .filter(
            PlatformCdasCredentialProfile.environment == env,
            func.lower(PlatformCdasCredentialProfile.username) == user.lower(),
            PlatformCdasCredentialProfile.company_id != company_id,
        )
        .first()
    )
    if duplicate:
        raise HTTPException(status_code=409, detail="This CDAS API username is already assigned to another LoanHub company in this environment")
    row = get_profile(db, company_id=company_id, environment=env)
    if not row:
        if not password:
            raise HTTPException(status_code=422, detail="A CDAS password is required for a new credential profile")
        row = PlatformCdasCredentialProfile(company_id=company_id, environment=env)
        db.add(row)
    row.base_url = url
    row.username = user
    row.item_code = str(item_code or "").strip() or None
    row.timeout_seconds = float(timeout_seconds)
    row.configured_by_user_id = configured_by_user_id
    if password:
        row.encrypted_password = _encrypt_password(password)
    row.last_test_status = None
    row.last_tested_at = None
    db.commit()
    db.refresh(row)
    return row


def profile_payload(row: PlatformCdasCredentialProfile | None) -> dict:
    if not row:
        return {"configured": False, "environment": None, "last_test_status": None, "last_tested_at": None}
    return {
        "id": str(row.id),
        "company_id": str(row.company_id),
        "environment": row.environment,
        "configured": bool(row.base_url and row.username and row.encrypted_password),
        "base_url": row.base_url,
        "username": row.username,
        "item_code": row.item_code,
        "timeout_seconds": float(row.timeout_seconds or 20),
        "password_configured": bool(row.encrypted_password),
        "last_test_status": row.last_test_status,
        "last_tested_at": row.last_tested_at,
    }


def public_profile_state(row: PlatformCdasCredentialProfile | None) -> dict:
    if not row:
        return {"configured": False, "last_test_status": None, "last_tested_at": None}
    return {
        "configured": bool(row.base_url and row.username and row.encrypted_password),
        "last_test_status": row.last_test_status,
        "last_tested_at": row.last_tested_at,
    }


def outstanding_balance(db: Session, *, company_id: UUID) -> Decimal:
    value = (
        db.query(func.coalesce(func.sum(PlatformCdasTransaction.amount), 0))
        .filter(
            PlatformCdasTransaction.company_id == company_id,
            PlatformCdasTransaction.status.in_(("accrued", "invoiced")),
        )
        .scalar()
        or Decimal("0")
    )
    return _money(value)


def usage_summary(db: Session, *, company_id: UUID) -> dict:
    subscription = get_subscription(db, company_id=company_id)
    outstanding = outstanding_balance(db, company_id=company_id)
    count = (
        db.query(func.count(PlatformCdasTransaction.id))
        .filter(
            PlatformCdasTransaction.company_id == company_id,
            PlatformCdasTransaction.environment == "live",
            PlatformCdasTransaction.status != "waived",
        )
        .scalar()
        or 0
    )
    limit = _money(subscription.credit_limit) if subscription and subscription.credit_limit is not None else None
    remaining = max(Decimal("0"), limit - outstanding) if limit is not None else None
    return {
        "live_transaction_count": int(count),
        "outstanding_balance": float(outstanding),
        "credit_limit": float(limit) if limit is not None else None,
        "remaining_credit": float(remaining) if remaining is not None else None,
        "currency": subscription.currency if subscription else "LSL",
    }


def _notify_company_owners(
    db: Session,
    *,
    company_id: UUID,
    title: str,
    message: str,
    event_type: str,
    entity_type: str = "cdas_subscription",
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
        key = f"{deduplication_key}:{owner.user_id}" if deduplication_key else None
        if key and db.query(Notification).filter(
            Notification.user_id == owner.user_id,
            Notification.deduplication_key == key,
        ).first():
            continue
        db.add(Notification(
            user_id=owner.user_id,
            company_id=company_id,
            title=title,
            message=message,
            notification_type=NotificationType.SYSTEM,
            event_type=event_type,
            action="view",
            entity_type=entity_type,
            entity_id=entity_id,
            action_url="/company/settings",
            icon="wallet-cards",
            priority=priority,
            data={"provider": "cdas"},
            deduplication_key=key,
        ))


def assert_live_credit_available(
    db: Session,
    *,
    subscription: PlatformCdasSubscription,
    environment: str,
    operation_type: str,
) -> None:
    if environment != "live" or subscription.credit_limit is None:
        return
    price = _money(normalize_pricing(subscription.pricing).get(operation_type, 0))
    outstanding = outstanding_balance(db, company_id=subscription.company_id)
    limit = _money(subscription.credit_limit)
    if outstanding + price <= limit:
        return
    if subscription.auto_suspend_on_limit:
        subscription.status = "suspended"
        subscription.suspended_at = datetime.now(timezone.utc)
        _notify_company_owners(
            db,
            company_id=subscription.company_id,
            title="CDAS access automatically suspended",
            message=f"Live CDAS usage reached the approved credit limit of {subscription.currency} {limit:.2f}.",
            event_type="cdas.credit_limit.suspended",
            entity_id=str(subscription.id),
            priority="high",
            deduplication_key=f"cdas-limit-{subscription.id}-{limit}",
        )
        db.commit()
    raise HTTPException(
        status_code=402,
        detail=f"CDAS credit limit reached. Outstanding {subscription.currency} {outstanding:.2f}; next operation {subscription.currency} {price:.2f}; limit {subscription.currency} {limit:.2f}.",
    )


def record_successful_operation(
    db: Session,
    *,
    company_id: UUID,
    environment: str,
    operation_type: str,
    actor_user_id: UUID | None,
    billing_key: str,
    source_reference: str | None = None,
    metadata: dict | None = None,
) -> PlatformCdasTransaction:
    existing = (
        db.query(PlatformCdasTransaction)
        .filter(PlatformCdasTransaction.billing_key == billing_key)
        .first()
    )
    if existing:
        return existing
    subscription = require_approved_subscription(db, company_id=company_id)
    live = environment == "live"
    rate = _money(normalize_pricing(subscription.pricing).get(operation_type, 0)) if live else Decimal("0.00")
    row = PlatformCdasTransaction(
        company_id=company_id,
        subscription_id=subscription.id,
        environment=environment,
        operation_type=operation_type,
        billing_key=billing_key,
        transaction_reference=f"CDAS-{uuid4().hex[:22].upper()}",
        unit_price=rate,
        amount=rate,
        currency=subscription.currency or "LSL",
        status="accrued" if live and rate > 0 else ("free_live" if live else "test"),
        actor_user_id=actor_user_id,
        source_reference=source_reference,
        accrued_at=datetime.now(timezone.utc),
        metadata_json={
            "billing_model": "pay_as_you_go",
            "business_operation_only": True,
            "environment": environment,
            "price_snapshot": float(rate),
            **(metadata or {}),
        },
    )
    db.add(row)
    db.flush()
    if live and rate > 0:
        from services.accounting_service import record_cdas_transaction_accrual
        record_cdas_transaction_accrual(db, row)
    if live and subscription.warning_threshold is not None:
        projected = outstanding_balance(db, company_id=company_id)
        threshold = _money(subscription.warning_threshold)
        if projected >= threshold:
            _notify_company_owners(
                db,
                company_id=company_id,
                title="CDAS spending warning",
                message=f"Outstanding Live CDAS usage has reached {subscription.currency} {projected:.2f}.",
                event_type="cdas.credit_limit.warning",
                entity_id=str(subscription.id),
                priority="high",
                deduplication_key=f"cdas-warning-{subscription.id}-{datetime.now(timezone.utc).strftime('%Y-%m')}",
            )
    db.commit()
    db.refresh(row)
    return row


def list_transactions(db: Session, *, company_id: UUID | None = None, limit: int = 200) -> list[dict]:
    query = db.query(PlatformCdasTransaction)
    if company_id is not None:
        query = query.filter(PlatformCdasTransaction.company_id == company_id)
    rows = query.order_by(PlatformCdasTransaction.accrued_at.desc()).limit(max(1, min(limit, 1000))).all()
    return [transaction_payload(row) for row in rows]



def waive_transaction(db: Session, *, transaction_id: UUID, reason: str) -> PlatformCdasTransaction:
    row = (
        db.query(PlatformCdasTransaction)
        .filter(PlatformCdasTransaction.id == transaction_id)
        .with_for_update()
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="CDAS transaction not found")
    if row.status != "accrued":
        raise HTTPException(
            status_code=409,
            detail="Only an accrued, not-yet-invoiced CDAS transaction can be waived",
        )
    row.status = "waived"
    row.waived_at = datetime.now(timezone.utc)
    row.waiver_reason = reason.strip()
    from services.accounting_service import reverse_cdas_transaction_accrual
    reverse_cdas_transaction_accrual(db, row)
    _notify_company_owners(
        db,
        company_id=row.company_id,
        title="CDAS charge waived",
        message=f"Charge {row.transaction_reference} for {row.currency} {_money(row.amount):.2f} was waived.",
        event_type="cdas.transaction.waived",
        entity_type="cdas_transaction",
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
) -> PlatformCdasTransaction:
    row = (
        db.query(PlatformCdasTransaction)
        .filter(PlatformCdasTransaction.id == transaction_id)
        .with_for_update()
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="CDAS transaction not found")
    if row.status == "refunded":
        return row
    if row.status != "settled":
        raise HTTPException(status_code=409, detail="Only a settled CDAS transaction can be refunded")
    method = payment_method.strip().lower()
    if method not in {"cash", "bank", "electronic"}:
        raise HTTPException(status_code=422, detail="Unsupported refund payment method")
    if method != "cash" and not (proof_reference or "").strip():
        raise HTTPException(status_code=422, detail="Non-cash refunds require proof_reference")
    row.status = "refunded"
    row.refunded_at = datetime.now(timezone.utc)
    row.refund_reason = reason.strip()
    metadata = dict(row.metadata_json or {})
    metadata["refund"] = {
        "payment_method": method,
        "proof_reference": (proof_reference or "").strip() or None,
        "recorded_at": row.refunded_at.isoformat(),
    }
    row.metadata_json = metadata
    from services.accounting_service import record_cdas_transaction_refund
    record_cdas_transaction_refund(db, row)
    _notify_company_owners(
        db,
        company_id=row.company_id,
        title="CDAS charge refunded",
        message=f"Charge {row.transaction_reference} for {row.currency} {_money(row.amount):.2f} has been refunded.",
        event_type="cdas.transaction.refunded",
        entity_type="cdas_transaction",
        entity_id=str(row.id),
        priority="normal",
    )
    db.commit()
    db.refresh(row)
    return row


def transaction_payload(row: PlatformCdasTransaction) -> dict:
    return {
        "id": str(row.id),
        "company_id": str(row.company_id),
        "subscription_id": str(row.subscription_id),
        "environment": row.environment,
        "operation_type": row.operation_type,
        "transaction_reference": row.transaction_reference,
        "unit_price": float(row.unit_price or 0),
        "amount": float(row.amount or 0),
        "currency": row.currency,
        "status": row.status,
        "source_reference": row.source_reference,
        "accrued_at": row.accrued_at,
        "settled_at": row.settled_at,
        "waived_at": row.waived_at,
        "waiver_reason": row.waiver_reason,
        "refunded_at": row.refunded_at,
        "refund_reason": row.refund_reason,
        "metadata": dict(row.metadata_json or {}),
    }


def create_invoice(db: Session, *, company_id: UUID, period_start: date, period_end: date) -> PlatformCdasInvoice:
    if period_end < period_start:
        raise HTTPException(status_code=422, detail="Invoice period end cannot be before period start")
    existing = db.query(PlatformCdasInvoice).filter(
        PlatformCdasInvoice.company_id == company_id,
        PlatformCdasInvoice.period_start == period_start,
        PlatformCdasInvoice.period_end == period_end,
    ).first()
    if existing:
        return existing
    subscription = get_subscription(db, company_id=company_id)
    if not subscription:
        raise HTTPException(status_code=404, detail="CDAS subscription not found")

    start_dt = datetime.combine(period_start, time.min, tzinfo=timezone.utc)
    end_dt = datetime.combine(period_end + timedelta(days=1), time.min, tzinfo=timezone.utc)
    rows = db.query(PlatformCdasTransaction).filter(
        PlatformCdasTransaction.company_id == company_id,
        PlatformCdasTransaction.environment == "live",
        PlatformCdasTransaction.accrued_at >= start_dt,
        PlatformCdasTransaction.accrued_at < end_dt,
        PlatformCdasTransaction.status.in_(("accrued", "waived")),
    ).order_by(PlatformCdasTransaction.accrued_at.asc()).with_for_update().all()

    subtotal = sum((_money(row.amount) for row in rows), Decimal("0"))
    waived = sum((_money(row.amount) for row in rows if row.status == "waived"), Decimal("0"))
    due = _money(subtotal - waived)
    issued_at = datetime.now(timezone.utc)
    invoice = PlatformCdasInvoice(
        company_id=company_id,
        subscription_id=subscription.id,
        invoice_number=f"CDI-{issued_at.strftime('%Y%m')}-{uuid4().hex[:10].upper()}",
        period_start=period_start,
        period_end=period_end,
        transaction_count=len(rows),
        subtotal=_money(subtotal),
        waived_amount=_money(waived),
        amount_due=due,
        currency=subscription.currency,
        status="issued" if due > 0 else "paid",
        issued_at=issued_at,
        due_at=issued_at + timedelta(days=int(subscription.billing_due_days or 14)),
        paid_at=issued_at if due <= 0 else None,
        snapshot={
            "transaction_ids": [str(row.id) for row in rows],
            "operation_pricing_is_snapshotted_per_transaction": True,
        },
    )
    db.add(invoice)
    db.flush()
    # Successful live operations are accrued individually; invoice creation
    # only groups those balances for settlement.
    for row in rows:
        if row.status == "accrued":
            row.status = "invoiced"
    _notify_company_owners(
        db,
        company_id=company_id,
        title="CDAS invoice issued",
        message=f"Invoice {invoice.invoice_number} totals {invoice.currency} {due:.2f}.",
        event_type="cdas.invoice.issued",
        entity_type="cdas_invoice",
        entity_id=str(invoice.id),
        priority="high" if due > 0 else "normal",
    )
    db.commit()
    db.refresh(invoice)
    return invoice


def invoice_payload(row: PlatformCdasInvoice) -> dict:
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
    query = db.query(PlatformCdasInvoice)
    if company_id is not None:
        query = query.filter(PlatformCdasInvoice.company_id == company_id)
    rows = query.order_by(PlatformCdasInvoice.issued_at.desc()).limit(max(1, min(limit, 500))).all()
    return [invoice_payload(row) for row in rows]


def mark_invoice_paid(
    db: Session,
    *,
    invoice_id: UUID,
    payment_method: str,
    proof_reference: str | None,
    notes: str | None = None,
) -> PlatformCdasInvoice:
    invoice = (
        db.query(PlatformCdasInvoice)
        .filter(PlatformCdasInvoice.id == invoice_id)
        .with_for_update()
        .first()
    )
    if not invoice:
        raise HTTPException(status_code=404, detail="CDAS invoice not found")
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
    from services.accounting_service import record_cdas_invoice_payment
    record_cdas_invoice_payment(db, invoice)
    transaction_ids = [UUID(value) for value in dict(invoice.snapshot or {}).get("transaction_ids", [])]
    if transaction_ids:
        rows = (
            db.query(PlatformCdasTransaction)
            .filter(
                PlatformCdasTransaction.id.in_(transaction_ids),
                PlatformCdasTransaction.status == "invoiced",
            )
            .order_by(PlatformCdasTransaction.id.asc())
            .with_for_update()
            .all()
        )
        for row in rows:
            row.status = "settled"
            row.settled_at = paid_at
    subscription = get_subscription(db, company_id=invoice.company_id)
    if subscription and subscription.status == "suspended" and subscription.auto_suspend_on_limit:
        other_overdue = db.query(PlatformCdasInvoice.id).filter(
            PlatformCdasInvoice.company_id == invoice.company_id,
            PlatformCdasInvoice.id != invoice.id,
            PlatformCdasInvoice.status == "issued",
            PlatformCdasInvoice.amount_due > 0,
            PlatformCdasInvoice.due_at < paid_at,
        ).first()
        within_credit = subscription.credit_limit is None or outstanding_balance(
            db, company_id=invoice.company_id
        ) < _money(subscription.credit_limit)
        if not other_overdue and within_credit:
            subscription.status = "approved"
            subscription.suspended_at = None
    _notify_company_owners(
        db,
        company_id=invoice.company_id,
        title="CDAS invoice paid",
        message=f"Invoice {invoice.invoice_number} has been marked paid.",
        event_type="cdas.invoice.paid",
        entity_type="cdas_invoice",
        entity_id=str(invoice.id),
    )
    db.commit()
    db.refresh(invoice)
    return invoice


def run_monthly_invoice_cycle(db: Session, *, now: datetime | None = None) -> int:
    now = now or datetime.now(timezone.utc)
    first_this_month = date(now.year, now.month, 1)
    previous_end = first_this_month - timedelta(days=1)
    previous_start = date(previous_end.year, previous_end.month, 1)
    subscriptions = db.query(PlatformCdasSubscription).filter(
        PlatformCdasSubscription.status.in_(("approved", "suspended")),
    ).all()
    issued = 0
    for subscription in subscriptions:
        existing = db.query(PlatformCdasInvoice).filter(
            PlatformCdasInvoice.company_id == subscription.company_id,
            PlatformCdasInvoice.period_start == previous_start,
            PlatformCdasInvoice.period_end == previous_end,
        ).first()
        if existing:
            continue
        live_count = db.query(func.count(PlatformCdasTransaction.id)).filter(
            PlatformCdasTransaction.company_id == subscription.company_id,
            PlatformCdasTransaction.environment == "live",
            PlatformCdasTransaction.accrued_at >= datetime.combine(previous_start, time.min, tzinfo=timezone.utc),
            PlatformCdasTransaction.accrued_at < datetime.combine(first_this_month, time.min, tzinfo=timezone.utc),
            PlatformCdasTransaction.status.in_(("accrued", "waived")),
        ).scalar() or 0
        if not live_count:
            continue
        create_invoice(db, company_id=subscription.company_id, period_start=previous_start, period_end=previous_end)
        issued += 1
    return issued


def suspend_overdue_accounts(db: Session, *, now: datetime | None = None) -> int:
    now = now or datetime.now(timezone.utc)
    overdue_company_ids = {
        company_id for (company_id,) in db.query(PlatformCdasInvoice.company_id).filter(
            PlatformCdasInvoice.status == "issued",
            PlatformCdasInvoice.amount_due > 0,
            PlatformCdasInvoice.due_at < now,
        ).all()
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
            title="CDAS access suspended for overdue invoice",
            message="Live CDAS access has been suspended because a PAYG invoice is overdue.",
            event_type="cdas.invoice.overdue_suspension",
            entity_id=str(subscription.id),
            priority="high",
            deduplication_key=f"cdas-overdue-{subscription.id}-{now.strftime('%Y-%m-%d')}",
        )
        suspended += 1
    if suspended:
        db.commit()
    return suspended
