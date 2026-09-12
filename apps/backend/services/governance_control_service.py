from __future__ import annotations

import hashlib
import secrets
from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

from database.models.enums import PaymentMethod, PaymentStatus
from database.models.governance_control import (
    AccountingPeriod,
    ApprovalRequest,
    BankStatementLine,
    PaymentAdjustment,
)
from database.models.payment import PaymentTransaction
from services.webhook_outbox_service import enqueue_webhook


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _money(value) -> Decimal:
    return Decimal(str(value or 0)).quantize(Decimal("0.01"))


def ensure_accounting_period_open(db: Session, *, company_id: UUID | None, entry_date: date) -> None:
    if company_id is None:
        return
    periods = db.query(AccountingPeriod).filter(AccountingPeriod.company_id == company_id)
    if periods.count() == 0:
        return
    period = periods.filter(
        AccountingPeriod.period_start <= entry_date,
        AccountingPeriod.period_end >= entry_date,
    ).first()
    if not period:
        raise HTTPException(status_code=409, detail="No accounting period is configured for this entry date")
    if period.status != "open":
        raise HTTPException(status_code=409, detail=f"Accounting period is {period.status}; posting is blocked")


def create_approval(
    db: Session,
    *,
    company_id: UUID,
    branch_id: UUID | None,
    action_type: str,
    resource_type: str,
    resource_id: str | None,
    payload: dict,
    idempotency_key: str,
    requested_by_user_id: UUID,
) -> ApprovalRequest:
    existing = db.query(ApprovalRequest).filter(
        ApprovalRequest.company_id == company_id,
        ApprovalRequest.idempotency_key == idempotency_key,
    ).first()
    if existing:
        return existing
    approval = ApprovalRequest(
        company_id=company_id,
        branch_id=branch_id,
        action_type=action_type,
        resource_type=resource_type,
        resource_id=resource_id,
        payload=payload,
        idempotency_key=idempotency_key,
        requested_by_user_id=requested_by_user_id,
    )
    db.add(approval)
    db.flush()
    return approval


def decide_approval(
    db: Session,
    *,
    approval: ApprovalRequest,
    user_id: UUID,
    approved: bool,
    reason: str,
) -> ApprovalRequest:
    if approval.status != "pending":
        raise HTTPException(status_code=409, detail="Approval request has already been decided")
    if approval.requested_by_user_id == user_id:
        raise HTTPException(status_code=409, detail="Maker/checker control: the requester cannot approve their own action")
    approval.status = "approved" if approved else "rejected"
    approval.decided_by_user_id = user_id
    approval.decision_reason = reason.strip()
    approval.decided_at = _now()
    db.add(approval)
    return approval


def request_payment_adjustment(
    db: Session,
    *,
    company_id: UUID,
    branch_id: UUID | None,
    payment: PaymentTransaction,
    adjustment_type: str,
    amount: Decimal,
    reason: str,
    idempotency_key: str,
    requested_by_user_id: UUID,
) -> PaymentAdjustment:
    if payment.company_id != company_id:
        raise HTTPException(status_code=404, detail="Payment was not found in the active company")
    if payment.status != PaymentStatus.SUCCEEDED:
        raise HTTPException(status_code=409, detail="Only a succeeded payment can be adjusted")
    if adjustment_type not in {"refund", "reversal", "chargeback"}:
        raise HTTPException(status_code=422, detail="Unsupported payment adjustment type")
    value = _money(amount)
    if value <= 0 or value > _money(payment.amount):
        raise HTTPException(status_code=422, detail="Adjustment amount must be positive and no greater than the payment")
    # Loan allocations and accounting postings are indivisible today. Refusing
    # partial reversals prevents the ledger and repayment schedule diverging.
    if adjustment_type in {"refund", "reversal"} and value != _money(payment.amount):
        raise HTTPException(status_code=422, detail="LoanHub currently requires a full-payment refund or reversal")
    existing = db.query(PaymentAdjustment).filter(
        PaymentAdjustment.company_id == company_id,
        PaymentAdjustment.idempotency_key == idempotency_key,
    ).first()
    if existing:
        return existing
    active = db.query(PaymentAdjustment).filter(
        PaymentAdjustment.payment_id == payment.id,
        PaymentAdjustment.status.in_(["pending_approval", "approved", "processing", "completed", "under_investigation"]),
    ).first()
    if active:
        raise HTTPException(status_code=409, detail="This payment already has an active adjustment")
    approval = create_approval(
        db,
        company_id=company_id,
        branch_id=branch_id,
        action_type=f"payment_{adjustment_type}",
        resource_type="payment_transaction",
        resource_id=str(payment.id),
        payload={"amount": str(value), "currency": payment.currency, "reason": reason.strip()},
        idempotency_key=f"approval:{idempotency_key}",
        requested_by_user_id=requested_by_user_id,
    )
    adjustment = PaymentAdjustment(
        company_id=company_id,
        payment_id=payment.id,
        approval_request_id=approval.id,
        adjustment_type=adjustment_type,
        amount=value,
        currency=payment.currency,
        reason=reason.strip(),
        idempotency_key=idempotency_key,
        requested_by_user_id=requested_by_user_id,
    )
    db.add(adjustment)
    db.flush()
    return adjustment


def approve_payment_adjustment(
    db: Session,
    *,
    adjustment: PaymentAdjustment,
    checker_user_id: UUID,
    reason: str,
) -> PaymentAdjustment:
    if adjustment.status != "pending_approval":
        raise HTTPException(status_code=409, detail="Payment adjustment is not awaiting approval")
    approval = db.get(ApprovalRequest, adjustment.approval_request_id)
    if not approval:
        raise HTTPException(status_code=409, detail="Approval record is missing")
    decide_approval(db, approval=approval, user_id=checker_user_id, approved=True, reason=reason)
    payment = db.get(PaymentTransaction, adjustment.payment_id)
    if not payment or payment.status != PaymentStatus.SUCCEEDED:
        raise HTTPException(status_code=409, detail="The source payment can no longer be adjusted")
    adjustment.approved_by_user_id = checker_user_id
    adjustment.approved_at = _now()
    if adjustment.adjustment_type == "chargeback":
        adjustment.status = "under_investigation"
    elif payment.payment_method == PaymentMethod.CASH:
        from services.loan_service import reverse_loan_payment
        from services.accounting_service import record_reversal_accounting

        reverse_loan_payment(db, payment)
        record_reversal_accounting(db, payment)
        payment.status = PaymentStatus.REVERSED
        payment.completed_at = _now()
        adjustment.status = "completed"
        adjustment.completed_at = _now()
        db.add(payment)
    else:
        # External movement must be confirmed by LelefaPayGate before LoanHub
        # changes the loan schedule or books the reversal.
        adjustment.status = "processing"
    db.add(adjustment)
    enqueue_webhook(
        db,
        company_id=adjustment.company_id,
        event_type="payment.adjustment.updated",
        aggregate_type="payment_adjustment",
        aggregate_id=str(adjustment.id),
        idempotency_key=f"payment-adjustment:{adjustment.id}:{adjustment.status}",
        payload={
            "id": str(adjustment.id),
            "payment_id": str(adjustment.payment_id),
            "type": adjustment.adjustment_type,
            "amount": str(adjustment.amount),
            "currency": adjustment.currency,
            "status": adjustment.status,
        },
    )
    return adjustment


def reject_payment_adjustment(db: Session, *, adjustment: PaymentAdjustment, checker_user_id: UUID, reason: str) -> PaymentAdjustment:
    if adjustment.status != "pending_approval":
        raise HTTPException(status_code=409, detail="Payment adjustment is not awaiting approval")
    approval = db.get(ApprovalRequest, adjustment.approval_request_id)
    if not approval:
        raise HTTPException(status_code=409, detail="Approval record is missing")
    decide_approval(db, approval=approval, user_id=checker_user_id, approved=False, reason=reason)
    adjustment.status = "rejected"
    adjustment.failure_reason = reason.strip()
    db.add(adjustment)
    return adjustment


def confirm_gateway_adjustment(
    db: Session,
    *,
    adjustment: PaymentAdjustment,
    provider_reference: str,
) -> PaymentAdjustment:
    if adjustment.status != "processing":
        raise HTTPException(status_code=409, detail="Adjustment is not awaiting gateway confirmation")
    payment = db.get(PaymentTransaction, adjustment.payment_id)
    if not payment or payment.status != PaymentStatus.SUCCEEDED:
        raise HTTPException(status_code=409, detail="Source payment is unavailable")
    from services.loan_service import reverse_loan_payment
    from services.accounting_service import record_reversal_accounting

    reverse_loan_payment(db, payment)
    record_reversal_accounting(db, payment)
    payment.status = PaymentStatus.REVERSED
    payment.completed_at = _now()
    adjustment.provider_reference = provider_reference.strip()
    adjustment.status = "completed"
    adjustment.completed_at = _now()
    db.add(payment)
    db.add(adjustment)
    return adjustment


def bank_line_fingerprint(*, company_id: UUID, account_reference: str | None, transaction_date: date, description: str, reference: str | None, amount: Decimal) -> str:
    raw = "|".join([str(company_id), (account_reference or "").strip(), transaction_date.isoformat(), description.strip(), (reference or "").strip(), str(_money(amount))])
    return hashlib.sha256(raw.encode()).hexdigest()


def match_bank_line(db: Session, *, line: BankStatementLine, payment: PaymentTransaction, user_id: UUID) -> BankStatementLine:
    if payment.company_id != line.company_id:
        raise HTTPException(status_code=404, detail="Payment is outside the bank-line company")
    if payment.status != PaymentStatus.SUCCEEDED or _money(payment.amount) != abs(_money(line.amount)):
        raise HTTPException(status_code=409, detail="Payment status or amount does not match the statement line")
    if db.query(BankStatementLine.id).filter(BankStatementLine.matched_payment_id == payment.id, BankStatementLine.id != line.id).first():
        raise HTTPException(status_code=409, detail="Payment is already matched to another statement line")
    line.matched_payment_id = payment.id
    line.matched_by_user_id = user_id
    line.matched_at = _now()
    line.status = "matched"
    db.add(line)
    return line


def new_case_reference(prefix: str) -> str:
    return f"{prefix}-{date.today():%Y%m%d}-{secrets.token_hex(4).upper()}"
