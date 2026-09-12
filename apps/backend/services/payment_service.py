from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

from database.models.cash import CashTransaction
from database.models.enums import (
    PaymentDirection,
    PaymentMethod,
    PaymentProvider,
    PaymentPurpose,
    PaymentStatus,
)
from database.models.payment import PaymentTransaction
from services.accounting_service import record_payment_accounting


OUTBOUND_PURPOSES = {
    PaymentPurpose.ASSISTED_BORROWER_ACCOUNT_FEE,
    PaymentPurpose.SUBSCRIPTION,
    PaymentPurpose.MARKETPLACE_UNLOCK,
    PaymentPurpose.LOAN_DISBURSEMENT,
    PaymentPurpose.PLATFORM_FEE,
    PaymentPurpose.PLATFORM_TRANSACTION_CHARGE,
    PaymentPurpose.PLATFORM_CLAIM_SETTLEMENT,
    PaymentPurpose.REFUND,
    PaymentPurpose.BUSINESS_PAYMENT,
}

PROVIDER_DEFAULT_METHOD: dict[PaymentProvider, PaymentMethod] = {
    PaymentProvider.CASH: PaymentMethod.CASH,
    PaymentProvider.LELEFAPAYGATE: PaymentMethod.LELEFAPAYGATE,
    PaymentProvider.MPESA: PaymentMethod.MPESA_WALLET,
    PaymentProvider.ECOCASH: PaymentMethod.ECOCASH_WALLET,
    PaymentProvider.EFT: PaymentMethod.BANK,
    PaymentProvider.MANUAL: PaymentMethod.BANK,
    PaymentProvider.MOCK: PaymentMethod.BANK,
}


def build_idempotency_key(*parts: Any) -> str:
    normalized = ":".join(str(part) for part in parts if part is not None)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _payment_reference(direction: PaymentDirection, method: PaymentMethod) -> str:
    prefix = "CIN" if direction == PaymentDirection.INBOUND else "COUT"
    if method != PaymentMethod.CASH:
        prefix = "PIN" if direction == PaymentDirection.INBOUND else "POUT"
    return f"{prefix}-{method.value.upper()}-{datetime.now(timezone.utc):%Y%m%d%H%M%S}-{uuid.uuid4().hex[:6].upper()}"


def initiate_payment(
    db: Session,
    *,
    provider: PaymentProvider,
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
    payment_method: PaymentMethod | None = None,
    proof_reference: str | None = None,
    proof_url: str | None = None,
    proof_notes: str | None = None,
    branch_id: UUID | None = None,
    **_: Any,
) -> PaymentTransaction:
    """Post cash locally or delegate every electronic movement to LelefaPayGate."""
    value = Decimal(str(amount)).quantize(Decimal("0.01"))
    if value <= 0:
        raise HTTPException(status_code=422, detail="Payment amount must be greater than zero")

    method = payment_method or PROVIDER_DEFAULT_METHOD.get(provider, PaymentMethod.CASH)
    if method == PaymentMethod.LELEFAPAYGATE:
        from services.lelefa_paygate_service import initiate_gateway_payment

        return initiate_gateway_payment(
            db,
            purpose=purpose,
            amount=value,
            idempotency_key=idempotency_key,
            initiated_by_user_id=initiated_by_user_id,
            company_id=company_id,
            borrower_id=borrower_id,
            loan_request_id=loan_request_id,
            loan_id=loan_id,
            direct_application_id=direct_application_id,
            company_borrower_account_id=company_borrower_account_id,
            payer_phone=payer_phone,
            payee_phone=payee_phone,
            branch_id=branch_id,
        )
    if method != PaymentMethod.CASH:
        raise HTTPException(
            status_code=422,
            detail="Direct electronic handlers were retired; use LelefaPayGate or cash",
        )

    existing = db.query(PaymentTransaction).filter(PaymentTransaction.idempotency_key == idempotency_key).first()
    if existing:
        return existing

    direction = PaymentDirection.OUTBOUND if purpose in OUTBOUND_PURPOSES else PaymentDirection.INBOUND
    # provider_reference is LoanHub's unique posting reference. The external bank,
    # wallet or POS reference is kept separately in proof_reference and may be reused.
    reference = _payment_reference(direction, method)
    now = datetime.now(timezone.utc)
    transaction = PaymentTransaction(
        company_id=company_id,
        borrower_id=borrower_id,
        loan_request_id=loan_request_id,
        loan_id=loan_id,
        direct_application_id=direct_application_id,
        company_borrower_account_id=company_borrower_account_id,
        initiated_by_user_id=initiated_by_user_id,
        provider=PaymentProvider.CASH if method == PaymentMethod.CASH else PaymentProvider.MANUAL,
        payment_method=method,
        direction=direction,
        purpose=purpose,
        status=PaymentStatus.SUCCEEDED,
        amount=value,
        currency="LSL",
        payer_phone=payer_phone,
        payee_phone=payee_phone,
        idempotency_key=idempotency_key,
        provider_reference=reference,
        proof_reference=(proof_reference or "").strip() or None,
        proof_url=(proof_url or "").strip() or None,
        proof_notes=(proof_notes or "").strip() or None,
        verified_by_user_id=initiated_by_user_id,
        verified_at=now,
        provider_payload={"method": method.value, "evidence_based": method != PaymentMethod.CASH},
        completed_at=now,
    )
    db.add(transaction)
    db.flush()

    if method == PaymentMethod.CASH:
        db.add(CashTransaction(
            payment_id=transaction.id,
            branch_id=branch_id,
            handled_by_user_id=initiated_by_user_id,
            direction=direction,
            cash_reference=reference,
            tendered_amount=value,
            applied_amount=value,
            change_amount=0,
            forward_amount=0,
            notes=f"Cash {purpose.value.replace('_', ' ')}",
        ))

    record_payment_accounting(db, transaction)
    from services.platform_finance_service import finalize_cash_finance_payment
    from services.billing_service import finalize_billing_payment
    from services.treasury_service import record_payment_treasury_entry

    finalize_cash_finance_payment(db, transaction)
    finalize_billing_payment(db, transaction)
    record_payment_treasury_entry(db, transaction, branch_id=branch_id)
    if transaction.company_id:
        from services.webhook_outbox_service import enqueue_webhook

        enqueue_webhook(
            db,
            company_id=transaction.company_id,
            event_type="payment.succeeded",
            aggregate_type="payment_transaction",
            aggregate_id=str(transaction.id),
            idempotency_key=f"payment:{transaction.id}:succeeded",
            payload={
                "id": str(transaction.id),
                "provider_reference": transaction.provider_reference,
                "purpose": transaction.purpose.value,
                "direction": transaction.direction.value,
                "amount": str(transaction.amount),
                "currency": transaction.currency,
                "status": transaction.status.value,
                "loan_id": str(transaction.loan_id) if transaction.loan_id else None,
                "borrower_id": str(transaction.borrower_id) if transaction.borrower_id else None,
            },
        )
    db.commit()
    db.refresh(transaction)
    return transaction


def apply_callback(*args, **kwargs):
    raise HTTPException(
        status_code=410,
        detail="Electronic payment callbacks are disabled until a provider adapter is configured",
    )
