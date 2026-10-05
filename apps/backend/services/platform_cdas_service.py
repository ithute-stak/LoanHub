from __future__ import annotations

import json
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from urllib.parse import urlparse
from uuid import UUID, uuid4

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from database.models.platform_cdas import (
    PlatformCdasCredentialProfile,
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
    now = datetime.now(timezone.utc)
    row.reviewed_by_user_id = reviewer_user_id
    row.reviewed_at = now
    row.approved_at = now if normalized == "approved" else row.approved_at
    row.suspended_at = now if normalized == "suspended" else None
    row.rejection_reason = reason if normalized == "rejected" else None
    row.notes = notes
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
            PlatformCdasTransaction.status == "accrued",
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
    db.commit()
    db.refresh(row)
    return row


def list_transactions(db: Session, *, company_id: UUID | None = None, limit: int = 200) -> list[dict]:
    query = db.query(PlatformCdasTransaction)
    if company_id is not None:
        query = query.filter(PlatformCdasTransaction.company_id == company_id)
    rows = query.order_by(PlatformCdasTransaction.accrued_at.desc()).limit(max(1, min(limit, 1000))).all()
    return [
        {
            "id": str(row.id),
            "company_id": str(row.company_id),
            "environment": row.environment,
            "operation_type": row.operation_type,
            "transaction_reference": row.transaction_reference,
            "unit_price": float(row.unit_price or 0),
            "amount": float(row.amount or 0),
            "currency": row.currency,
            "status": row.status,
            "source_reference": row.source_reference,
            "accrued_at": row.accrued_at,
            "metadata": dict(row.metadata_json or {}),
        }
        for row in rows
    ]
