from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from urllib.parse import urlparse
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

from database.config.config import settings
from database.models.borrower import Borrower
from database.models.client_loan_company import ClientCompanyLoan
from database.models.enums import (
    LoanStatus,
    PaymentDirection,
    PaymentMethod,
    PaymentProvider,
    PaymentPurpose,
    PaymentStatus,
)
from database.models.early_settlement import LoanEarlySettlement
from database.models.lelefa_paygate import LelefaPayGateWebhookEvent
from database.models.origination import LoanTopUpSettlement
from database.models.payment import PaymentTransaction
from integrations.lelefa_paygate import LelefaPayGateClient, LelefaPayGateError
from services.accounting_service import record_payment_accounting, record_reversal_accounting
from services.webhook_outbox_service import enqueue_webhook


SUCCESS_STATES = {"succeeded", "completed"}
FAILURE_STATES = {"failed", "cancelled", "expired"}
PROCESSING_STATES = {
    "created", "requires_confirmation", "awaiting_customer", "processing", "unknown", "open",
}
PAYOUT_PURPOSES = {
    PaymentPurpose.LOAN_DISBURSEMENT,
    PaymentPurpose.REFUND,
    PaymentPurpose.BUSINESS_PAYMENT,
    PaymentPurpose.PLATFORM_CLAIM_SETTLEMENT,
}


def _enqueue_payment_event(db: Session, payment: PaymentTransaction) -> None:
    if not payment.company_id:
        return
    status_value = payment.status.value if hasattr(payment.status, "value") else str(payment.status)
    enqueue_webhook(
        db,
        company_id=payment.company_id,
        event_type=f"payment.{status_value}",
        aggregate_type="payment_transaction",
        aggregate_id=str(payment.id),
        idempotency_key=f"payment:{payment.id}:{status_value}",
        payload={
            "id": str(payment.id),
            "provider_reference": payment.provider_reference,
            "purpose": payment.purpose.value,
            "direction": payment.direction.value,
            "amount": str(payment.amount),
            "currency": payment.currency,
            "status": status_value,
            "loan_id": str(payment.loan_id) if payment.loan_id else None,
            "borrower_id": str(payment.borrower_id) if payment.borrower_id else None,
        },
    )


def _money(value: Decimal | str | int | float) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"))


def _gateway_status(value: str | None) -> PaymentStatus:
    status = (value or "").strip().lower()
    if status in SUCCESS_STATES:
        return PaymentStatus.SUCCEEDED
    if status == "reversed":
        return PaymentStatus.REVERSED
    if status == "cancelled":
        return PaymentStatus.CANCELLED
    if status in FAILURE_STATES:
        return PaymentStatus.FAILED
    return PaymentStatus.PROCESSING


def _borrower_phone(db: Session, borrower_id: UUID | None) -> str | None:
    borrower = db.get(Borrower, borrower_id) if borrower_id else None
    phone = borrower.user.phone if borrower and borrower.user else None
    return phone.strip() if phone else None


def _safe_gateway_payload(
    *,
    response: dict[str, Any] | None,
    resource_type: str,
    branch_id: UUID | None,
    internal_reference: str,
    integration_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    response = response or {}
    return {
        **(integration_context or {}),
        "gateway": "lelefapaygate",
        "resource_type": resource_type,
        "gateway_status": response.get("status"),
        "gateway_public_id": response.get("public_id") or response.get("id"),
        "provider": response.get("provider"),
        "checkout_url": response.get("checkout_url"),
        "branch_id": str(branch_id) if branch_id else None,
        "internal_reference": internal_reference,
    }


def _finalize_top_up(db: Session, payment: PaymentTransaction) -> None:
    loan = payment.loan or db.get(ClientCompanyLoan, payment.loan_id)
    if not loan or not loan.is_top_up:
        return
    existing = (
        db.query(LoanTopUpSettlement)
        .filter(LoanTopUpSettlement.new_loan_id == loan.id)
        .first()
    )
    if existing:
        return
    if not loan.parent_loan_id:
        raise HTTPException(status_code=409, detail="Top-up loan is missing its parent loan")

    parent = (
        db.query(ClientCompanyLoan)
        .filter(ClientCompanyLoan.id == loan.parent_loan_id)
        .with_for_update()
        .first()
    )
    if not parent or parent.status not in {LoanStatus.ACTIVE, LoanStatus.DEFAULTED}:
        raise HTTPException(status_code=409, detail="The original loan is not eligible for top-up settlement")
    settlement_amount = _money(parent.balance)
    if abs(settlement_amount - _money(loan.top_up_settlement_amount)) > Decimal("0.01"):
        raise HTTPException(
            status_code=409,
            detail="The original loan balance changed after top-up approval; reassess the top-up",
        )
    now = payment.completed_at or datetime.now(timezone.utc)
    db.add(
        LoanTopUpSettlement(
            company_id=loan.company_id,
            borrower_id=loan.borrower_id,
            parent_loan_id=parent.id,
            new_loan_id=loan.id,
            settlement_amount=settlement_amount,
            cash_to_borrower=_money(payment.amount),
            parent_balance_before=_money(parent.balance),
            parent_amount_paid_before=_money(parent.amount_paid),
            parent_status_before=parent.status.value if hasattr(parent.status, "value") else str(parent.status),
            status="settled",
            settled_at=now,
            settled_by_user_id=payment.initiated_by_user_id,
            notes=f"Original loan {parent.loan_reference} settled from top-up {loan.loan_reference}",
        )
    )
    parent.amount_paid = _money(parent.total_repayable)
    parent.balance = _money(0)
    parent.status = LoanStatus.COMPLETED


def finalize_gateway_payment(db: Session, payment: PaymentTransaction) -> PaymentTransaction:
    """Post downstream loan/accounting effects once, only after gateway success."""
    settlement_id = (payment.provider_payload or {}).get("early_settlement_id")
    if payment.status == PaymentStatus.SUCCEEDED:
        if settlement_id:
            from services.early_settlement_service import finalize_early_settlement_payment

            finalize_early_settlement_payment(db, payment)
        _enqueue_payment_event(db, payment)
        return payment

    payment.status = PaymentStatus.SUCCEEDED
    payment.verified_at = datetime.now(timezone.utc)
    payment.completed_at = payment.verified_at
    payment.failure_reason = None
    db.add(payment)
    db.flush()

    from services.loan_service import finalize_loan_payment
    from services.platform_finance_service import (
        accrue_platform_transaction_charge,
        finalize_cash_finance_payment,
    )
    from services.billing_service import finalize_billing_payment
    from services.receipt_service import ensure_payment_receipt
    from services.treasury_service import record_payment_treasury_entry

    if payment.purpose == PaymentPurpose.LOAN_DISBURSEMENT:
        _finalize_top_up(db, payment)
    if settlement_id:
        from services.early_settlement_service import finalize_early_settlement_payment

        finalize_early_settlement_payment(db, payment)
        _enqueue_payment_event(db, payment)
        return payment
    finalize_loan_payment(db, payment, commit=False)
    record_payment_accounting(db, payment)
    finalize_cash_finance_payment(db, payment)
    finalize_billing_payment(db, payment)
    accrue_platform_transaction_charge(db, payment)
    if payment.loan_id:
        ensure_payment_receipt(db, payment)
    branch_id = (payment.provider_payload or {}).get("branch_id")
    record_payment_treasury_entry(
        db,
        payment,
        branch_id=UUID(branch_id) if branch_id else None,
        description=f"LelefaPayGate {payment.purpose.value.replace('_', ' ')}",
    )
    _enqueue_payment_event(db, payment)
    return payment


def initiate_gateway_payment(
    db: Session,
    *,
    purpose: PaymentPurpose,
    amount: Decimal,
    idempotency_key: str,
    initiated_by_user_id: UUID | None,
    company_id: UUID | None = None,
    borrower_id: UUID | None = None,
    loan_request_id: UUID | None = None,
    loan_id: UUID | None = None,
    direct_application_id: UUID | None = None,
    company_borrower_account_id: UUID | None = None,
    payer_phone: str | None = None,
    payee_phone: str | None = None,
    branch_id: UUID | None = None,
    reference: str | None = None,
    integration_context: dict[str, Any] | None = None,
    gateway_provider: str | None = None,
) -> PaymentTransaction:
    value = _money(amount)
    if value <= 0:
        raise HTTPException(status_code=422, detail="Payment amount must be greater than zero")
    existing = (
        db.query(PaymentTransaction)
        .filter(PaymentTransaction.idempotency_key == idempotency_key)
        .first()
    )
    if existing:
        return existing
    if not settings.LELEFAPAYGATE_ENABLED:
        raise HTTPException(status_code=503, detail="LelefaPayGate is not enabled for LoanHub")

    is_payout = purpose in PAYOUT_PURPOSES
    selected_provider = None
    try:
        client = LelefaPayGateClient()
        if not is_payout:
            selected_provider = (
                gateway_provider or settings.LELEFAPAYGATE_COLLECTION_PROVIDER
            ).strip().lower()
            catalog = client.list_payment_methods(currency="LSL")
            methods = catalog.get("methods") if isinstance(catalog.get("methods"), list) else []
            available = next(
                (
                    method for method in methods
                    if isinstance(method, dict)
                    and method.get("id") == selected_provider
                    and method.get("provider") == selected_provider
                    and method.get("flow") == "phone_prompt"
                    and method.get("available") is True
                ),
                None,
            )
            if not available:
                raise HTTPException(
                    status_code=422,
                    detail="The selected LelefaPayGate provider is not available for LSL collections",
                )
    except LelefaPayGateError as exc:
        raise HTTPException(
            status_code=exc.status_code or 502,
            detail=f"Could not load LelefaPayGate payment methods: {exc.detail}",
        ) from exc

    phone = (payee_phone if is_payout else payer_phone) or _borrower_phone(db, borrower_id)
    if not phone:
        raise HTTPException(
            status_code=422,
            detail="A verified customer phone number is required for LelefaPayGate",
        )

    direction = PaymentDirection.OUTBOUND if is_payout else PaymentDirection.INBOUND
    operation = "payout" if is_payout else "payment_intent"
    internal_reference = (reference or f"LH-{purpose.value}-{uuid.uuid4().hex[:12]}")[:100]
    pending_reference = f"LPG-PENDING-{uuid.uuid4().hex.upper()}"
    payment = PaymentTransaction(
        company_id=company_id,
        borrower_id=borrower_id,
        loan_request_id=loan_request_id,
        loan_id=loan_id,
        direct_application_id=direct_application_id,
        company_borrower_account_id=company_borrower_account_id,
        initiated_by_user_id=initiated_by_user_id,
        provider=PaymentProvider.LELEFAPAYGATE,
        payment_method=PaymentMethod.LELEFAPAYGATE,
        direction=direction,
        purpose=purpose,
        status=PaymentStatus.PROCESSING,
        amount=value,
        currency="LSL",
        payer_phone=phone if not is_payout else payer_phone,
        payee_phone=phone if is_payout else payee_phone,
        configuration_scope="server",
        provider_operation=operation,
        idempotency_key=idempotency_key,
        provider_reference=pending_reference,
        provider_payload=_safe_gateway_payload(
            response=None,
            resource_type=operation,
            branch_id=branch_id,
            internal_reference=internal_reference,
            integration_context=integration_context,
        ),
    )
    db.add(payment)
    db.commit()
    db.refresh(payment)

    metadata = {
        **(integration_context or {}),
        "source": "LoanHub",
        "loanhub_payment_id": str(payment.id),
        "company_id": str(company_id) if company_id else None,
        "borrower_id": str(borrower_id) if borrower_id else None,
        "loan_id": str(loan_id) if loan_id else None,
        "purpose": purpose.value,
    }
    try:
        if is_payout:
            response = client.create_payout(
                amount=f"{value:.2f}",
                phone=phone,
                reference=internal_reference,
                metadata=metadata,
                idempotency_key=idempotency_key,
            )
        else:
            response = client.create_payment_intent(
                amount=f"{value:.2f}",
                phone=phone,
                reference=internal_reference,
                metadata=metadata,
                idempotency_key=idempotency_key,
                provider=selected_provider,
            )
    except LelefaPayGateError as exc:
        payment.failure_reason = exc.detail
        payment.status = PaymentStatus.PROCESSING if exc.retryable else PaymentStatus.FAILED
        db.add(payment)
        db.commit()
        db.refresh(payment)
        if not exc.retryable:
            raise HTTPException(
                status_code=exc.status_code or 502,
                detail=f"LelefaPayGate rejected the transaction: {exc.detail}",
            ) from exc
        return payment

    public_id = str(response.get("public_id") or response.get("id") or "").strip()
    if not public_id:
        payment.failure_reason = "Gateway response did not include a public resource ID"
        db.add(payment)
        db.commit()
        raise HTTPException(status_code=502, detail=payment.failure_reason)

    payment.provider_reference = public_id
    payment.provider_payload = _safe_gateway_payload(
        response=response,
        resource_type=operation,
        branch_id=branch_id,
        internal_reference=internal_reference,
        integration_context=integration_context,
    )
    mapped = _gateway_status(str(response.get("status") or "processing"))
    if mapped == PaymentStatus.SUCCEEDED:
        finalize_gateway_payment(db, payment)
    else:
        payment.status = mapped
        if mapped in {PaymentStatus.FAILED, PaymentStatus.CANCELLED}:
            payment.failure_reason = str(response.get("failure_message") or "Gateway transaction failed")[:1000]
    db.add(payment)
    db.commit()
    db.refresh(payment)
    return payment


def initiate_gateway_loan_repayment(
    db: Session,
    *,
    loan: ClientCompanyLoan,
    amount: Decimal,
    idempotency_key: str,
    initiated_by_user_id: UUID,
    gateway_provider: str | None = None,
    payer_phone: str | None = None,
) -> PaymentTransaction:
    return initiate_gateway_payment(
        db,
        purpose=PaymentPurpose.LOAN_REPAYMENT,
        amount=amount,
        idempotency_key=idempotency_key,
        initiated_by_user_id=initiated_by_user_id,
        company_id=loan.company_id,
        borrower_id=loan.borrower_id,
        loan_request_id=loan.loan_request_id,
        loan_id=loan.id,
        branch_id=loan.branch_id,
        reference=loan.loan_reference,
        gateway_provider=gateway_provider,
        payer_phone=payer_phone,
    )


def initiate_borrower_gateway_checkout(
    db: Session,
    *,
    loan: ClientCompanyLoan,
    amount: Decimal,
    idempotency_key: str,
    initiated_by_user_id: UUID,
) -> tuple[PaymentTransaction, str]:
    """Create a LoanHub payment record before opening hosted gateway checkout."""
    value = _money(amount)
    if value <= 0:
        raise HTTPException(status_code=422, detail="Payment amount must be greater than zero")
    existing = (
        db.query(PaymentTransaction)
        .filter(PaymentTransaction.idempotency_key == idempotency_key)
        .first()
    )
    if existing:
        checkout_url = str((existing.provider_payload or {}).get("checkout_url") or "")
        if checkout_url:
            return existing, checkout_url
        raise HTTPException(status_code=409, detail="The existing payment does not have a checkout URL")
    if not settings.LELEFAPAYGATE_ENABLED:
        raise HTTPException(status_code=503, detail="LelefaPayGate is not enabled for LoanHub")

    internal_reference = f"{loan.loan_reference}-ONLINE-{uuid.uuid4().hex[:8]}"
    pending_reference = f"LPG-PENDING-{uuid.uuid4().hex.upper()}"
    payment = PaymentTransaction(
        company_id=loan.company_id,
        borrower_id=loan.borrower_id,
        loan_request_id=loan.loan_request_id,
        loan_id=loan.id,
        initiated_by_user_id=initiated_by_user_id,
        provider=PaymentProvider.LELEFAPAYGATE,
        payment_method=PaymentMethod.LELEFAPAYGATE,
        direction=PaymentDirection.INBOUND,
        purpose=PaymentPurpose.LOAN_REPAYMENT,
        status=PaymentStatus.PROCESSING,
        amount=value,
        currency="LSL",
        configuration_scope="server",
        provider_operation="checkout_session",
        idempotency_key=idempotency_key,
        provider_reference=pending_reference,
        provider_payload=_safe_gateway_payload(
            response=None,
            resource_type="checkout_session",
            branch_id=loan.branch_id,
            internal_reference=internal_reference,
            integration_context={"hosted_checkout": True},
        ),
    )
    db.add(payment)
    db.commit()
    db.refresh(payment)

    metadata = {
        "source": "LoanHub",
        "hosted_checkout": True,
        "loanhub_payment_id": str(payment.id),
        "company_id": str(loan.company_id),
        "borrower_id": str(loan.borrower_id),
        "loan_id": str(loan.id),
        "purpose": PaymentPurpose.LOAN_REPAYMENT.value,
    }
    return_url = f"{settings.PUBLIC_APP_URL.rstrip('/')}/borrower/payments"
    try:
        response = LelefaPayGateClient().create_checkout_session(
            amount=f"{value:.2f}",
            reference=internal_reference,
            description=f"Loan repayment {loan.loan_reference}",
            metadata=metadata,
            idempotency_key=idempotency_key,
            success_url=f"{return_url}?checkout=success",
            cancel_url=f"{return_url}?checkout=cancelled",
        )
    except LelefaPayGateError as exc:
        payment.failure_reason = exc.detail
        payment.status = PaymentStatus.PROCESSING if exc.retryable else PaymentStatus.FAILED
        db.add(payment)
        db.commit()
        raise HTTPException(
            status_code=exc.status_code or 502,
            detail=f"Could not create LelefaPayGate checkout: {exc.detail}",
        ) from exc

    public_id = str(response.get("public_id") or response.get("id") or "").strip()
    checkout_url = str(response.get("checkout_url") or "").strip()
    parsed = urlparse(checkout_url)
    if not public_id or parsed.scheme not in {"http", "https"} or not parsed.netloc:
        payment.status = PaymentStatus.FAILED
        payment.failure_reason = "Gateway response did not include a valid hosted checkout"
        db.add(payment)
        db.commit()
        raise HTTPException(status_code=502, detail=payment.failure_reason)

    payment.provider_reference = public_id
    payment.provider_payload = _safe_gateway_payload(
        response=response,
        resource_type="checkout_session",
        branch_id=loan.branch_id,
        internal_reference=internal_reference,
        integration_context={"hosted_checkout": True},
    )
    payment.status = _gateway_status(str(response.get("status") or "open"))
    db.add(payment)
    db.commit()
    db.refresh(payment)
    return payment, checkout_url


def initiate_borrower_settlement_checkout(
    db: Session,
    *,
    loan: ClientCompanyLoan,
    quote: LoanEarlySettlement,
    idempotency_key: str,
    initiated_by_user_id: UUID,
    agreement_note: str,
    agreement_reference: str | None,
) -> tuple[PaymentTransaction, str]:
    """Open hosted checkout for the exact calculator-backed settlement quote."""
    locked = (
        db.query(LoanEarlySettlement)
        .filter(LoanEarlySettlement.id == quote.id, LoanEarlySettlement.loan_id == loan.id)
        .with_for_update()
        .first()
    )
    if not locked:
        raise HTTPException(status_code=404, detail="Early-settlement quote not found")
    if locked.status == "processing" and locked.payment_id:
        existing = db.get(PaymentTransaction, locked.payment_id)
        checkout_url = str((existing.provider_payload or {}).get("checkout_url") or "") if existing else ""
        if existing and checkout_url:
            return existing, checkout_url
    if locked.status != "quoted":
        raise HTTPException(status_code=409, detail="This settlement quote is no longer payable")
    now = datetime.now(timezone.utc)
    expires_at = locked.quote_expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < now:
        locked.status = "expired"
        db.commit()
        raise HTTPException(status_code=410, detail="The early-settlement quote has expired")
    if _money(loan.amount_paid) != _money(locked.original_amount_paid):
        raise HTTPException(status_code=409, detail="The loan changed after this quote; create a new quote")
    if _money(locked.settlement_amount) <= 0:
        raise HTTPException(status_code=409, detail="No settlement payment is due")

    locked.borrower_acknowledged = True
    locked.agreement_note = agreement_note.strip()
    locked.agreement_reference = (agreement_reference or "").strip() or None
    locked.status = "processing"
    db.add(locked)
    db.commit()
    try:
        payment, checkout_url = initiate_borrower_gateway_checkout(
            db,
            loan=loan,
            amount=_money(locked.settlement_amount),
            idempotency_key=idempotency_key,
            initiated_by_user_id=initiated_by_user_id,
        )
    except HTTPException:
        locked.status = "failed"
        db.add(locked)
        db.commit()
        raise

    payment.provider_payload = {
        **(payment.provider_payload or {}),
        "early_settlement_id": str(locked.id),
        "settlement_date": locked.settlement_date.isoformat(),
    }
    locked.payment_id = payment.id
    db.add(payment)
    db.add(locked)
    db.commit()
    db.refresh(payment)
    if payment.status == PaymentStatus.SUCCEEDED:
        finalize_gateway_payment(db, payment)
        db.commit()
    return payment, checkout_url


def initiate_gateway_loan_disbursement(
    db: Session,
    *,
    loan: ClientCompanyLoan,
    amount: Decimal,
    idempotency_key: str,
    initiated_by_user_id: UUID,
) -> PaymentTransaction:
    return initiate_gateway_payment(
        db,
        purpose=PaymentPurpose.LOAN_DISBURSEMENT,
        amount=amount,
        idempotency_key=idempotency_key,
        initiated_by_user_id=initiated_by_user_id,
        company_id=loan.company_id,
        borrower_id=loan.borrower_id,
        loan_request_id=loan.loan_request_id,
        loan_id=loan.id,
        branch_id=loan.branch_id,
        reference=loan.loan_reference,
    )


def apply_gateway_resource(
    db: Session,
    payment: PaymentTransaction,
    resource: dict[str, Any],
) -> PaymentTransaction:
    response_id = str(resource.get("public_id") or resource.get("id") or "")
    if response_id and payment.provider_reference.startswith("LPG-PENDING-"):
        payment.provider_reference = response_id
    status = _gateway_status(str(resource.get("status") or "processing"))
    payment.provider_payload = {
        **(payment.provider_payload or {}),
        "gateway_status": resource.get("status"),
        "gateway_public_id": response_id or payment.provider_reference,
        "provider": resource.get("provider"),
    }
    if status == PaymentStatus.SUCCEEDED:
        finalize_gateway_payment(db, payment)
    elif status == PaymentStatus.REVERSED and payment.status == PaymentStatus.SUCCEEDED:
        from services.loan_service import reverse_loan_payment
        reverse_loan_payment(db, payment)
        record_reversal_accounting(db, payment)
        payment.status = PaymentStatus.REVERSED
        payment.completed_at = datetime.now(timezone.utc)
    elif payment.status != PaymentStatus.SUCCEEDED:
        payment.status = status
        if status in {PaymentStatus.FAILED, PaymentStatus.CANCELLED}:
            payment.failure_reason = str(resource.get("failure_message") or "Gateway transaction failed")[:1000]
            settlement_id = (payment.provider_payload or {}).get("early_settlement_id")
            if settlement_id:
                from database.models.early_settlement import LoanEarlySettlement

                try:
                    quote = db.get(LoanEarlySettlement, UUID(str(settlement_id)))
                except ValueError:
                    quote = None
                if quote and quote.status == "processing":
                    quote.status = "failed"
                    db.add(quote)
    db.add(payment)
    _enqueue_payment_event(db, payment)
    db.commit()
    db.refresh(payment)
    return payment


def refresh_gateway_payment(db: Session, payment: PaymentTransaction) -> PaymentTransaction:
    if payment.provider != PaymentProvider.LELEFAPAYGATE:
        raise HTTPException(status_code=409, detail="This payment is not managed by LelefaPayGate")
    if payment.provider_reference.startswith("LPG-PENDING-"):
        raise HTTPException(
            status_code=409,
            detail="The gateway resource ID is unknown; reconcile using the stored idempotency key",
        )
    try:
        resource = LelefaPayGateClient().get_resource(
            payment.provider_operation or "",
            payment.provider_reference,
        )
    except LelefaPayGateError as exc:
        raise HTTPException(
            status_code=exc.status_code or 502,
            detail=f"Could not refresh LelefaPayGate status: {exc.detail}",
        ) from exc
    return apply_gateway_resource(db, payment, resource)


def process_gateway_webhook(
    db: Session,
    *,
    raw_body: bytes,
    event_id: str,
) -> tuple[LelefaPayGateWebhookEvent, bool]:
    payload_hash = hashlib.sha256(raw_body).hexdigest()
    existing = (
        db.query(LelefaPayGateWebhookEvent)
        .filter(LelefaPayGateWebhookEvent.event_id == event_id)
        .first()
    )
    if existing:
        if existing.payload_hash != payload_hash:
            raise HTTPException(status_code=409, detail="Webhook event ID was reused with different content")
        return existing, True

    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="Invalid webhook JSON") from exc
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Invalid webhook payload")

    event_type = str(payload.get("type") or "")
    event = LelefaPayGateWebhookEvent(
        event_id=event_id,
        event_type=event_type,
        payload_hash=payload_hash,
        payload=payload,
        processing_status="received",
    )
    db.add(event)
    db.flush()

    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    metadata = data.get("metadata") if isinstance(data.get("metadata"), dict) else {}
    payment = None
    payment_id = metadata.get("loanhub_payment_id")
    if payment_id:
        try:
            payment = db.get(PaymentTransaction, UUID(str(payment_id)))
        except ValueError:
            payment = None
    gateway_id = str(data.get("id") or "")
    if payment is None and gateway_id:
        payment = (
            db.query(PaymentTransaction)
            .filter(PaymentTransaction.provider_reference == gateway_id)
            .first()
        )
    if payment is None:
        event.processing_status = "ignored"
        event.processing_error = "No matching LoanHub payment"
        event.processed_at = datetime.now(timezone.utc)
        db.commit()
        return event, False

    event.payment_id = payment.id
    if data.get("amount") is not None and _money(data["amount"]) != _money(payment.amount):
        event.processing_status = "rejected"
        event.processing_error = "Gateway amount does not match LoanHub payment"
        event.processed_at = datetime.now(timezone.utc)
        db.commit()
        raise HTTPException(status_code=409, detail=event.processing_error)
    if data.get("currency") and str(data["currency"]).upper() != payment.currency:
        event.processing_status = "rejected"
        event.processing_error = "Gateway currency does not match LoanHub payment"
        event.processed_at = datetime.now(timezone.utc)
        db.commit()
        raise HTTPException(status_code=409, detail=event.processing_error)

    resource = {
        **data,
        "public_id": gateway_id or payment.provider_reference,
        "status": event_type.rsplit(".", 1)[-1],
    }
    apply_gateway_resource(db, payment, resource)
    event.processing_status = "processed"
    event.processed_at = datetime.now(timezone.utc)
    db.add(event)
    db.commit()
    db.refresh(event)
    return event, False
