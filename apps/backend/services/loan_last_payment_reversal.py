"""Controlled reversal of the latest *cash* loan repayment.

Never delete payment transactions or payment allocations: they form the audit trail.
Electronic refunds, early settlements, renewed schedules and closed treasury
periods require a separate reconciliation process.
"""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

from database.models.audit_log import AuditLog
from database.models.client_loan_company import ClientCompanyLoan
from database.models.enums import PaymentDirection, PaymentMethod, PaymentPurpose, PaymentStatus
from database.models.payment import PaymentTransaction
from database.models.treasury import TreasuryEntry
from services.accounting_service import record_reversal_accounting
from services.loan_service import reverse_loan_payment
from services.treasury_service import void_treasury_entry


def _last_payment_query(db: Session, loan: ClientCompanyLoan):
    return (
        db.query(PaymentTransaction)
        .filter(
            PaymentTransaction.company_id == loan.company_id,
            PaymentTransaction.loan_id == loan.id,
            PaymentTransaction.direction == PaymentDirection.INBOUND,
            PaymentTransaction.purpose.in_([PaymentPurpose.LOAN_REPAYMENT, PaymentPurpose.DIRECT_DEBIT]),
            PaymentTransaction.status.in_([PaymentStatus.SUCCEEDED, PaymentStatus.REVERSED]),
        )
        .order_by(PaymentTransaction.completed_at.desc(), PaymentTransaction.created_at.desc(), PaymentTransaction.id.desc())
    )


def latest_repayment(db: Session, loan: ClientCompanyLoan) -> dict | None:
    payment = _last_payment_query(db, loan).first()
    if payment is None:
        return None
    payload = payment.provider_payload or {}
    is_cash = payment.payment_method == PaymentMethod.CASH and payment.status == PaymentStatus.SUCCEEDED
    is_ordinary = payment.purpose == PaymentPurpose.LOAN_REPAYMENT and not payload.get("early_settlement_id")
    return {
        "payment_id": str(payment.id),
        "loan_id": str(loan.id),
        "reference": payment.provider_reference,
        "amount": str(payment.amount),
        "completed_at": payment.completed_at.isoformat() if payment.completed_at else None,
        "payment_method": payment.payment_method.value,
        "reversible": bool(is_cash and is_ordinary),
        "restriction": None if is_cash and is_ordinary else
            "Only ordinary cash repayments can be reversed here; electronic payments and settlements need separate reconciliation.",
    }


def reverse_latest_cash_repayment(
    db: Session,
    *,
    loan_id: UUID,
    company_id: UUID,
    payment_id: UUID,
    user_id: UUID,
    actor_role: str,
    reason: str,
) -> dict:
    reason = reason.strip()
    if len(reason) < 12:
        raise HTTPException(status_code=422, detail="Enter a specific reversal reason of at least 12 characters")

    # Serialise competing reversal and payment-update requests against the loan.
    loan = (
        db.query(ClientCompanyLoan)
        .filter(ClientCompanyLoan.id == loan_id, ClientCompanyLoan.company_id == company_id)
        .with_for_update()
        .first()
    )
    if loan is None:
        raise HTTPException(status_code=404, detail="Loan not found")

    payment = (
        db.query(PaymentTransaction)
        .filter(
            PaymentTransaction.id == payment_id,
            PaymentTransaction.loan_id == loan_id,
            PaymentTransaction.company_id == company_id,
        )
        .with_for_update()
        .first()
    )
    if payment is None:
        raise HTTPException(status_code=404, detail="Payment not found for this loan")
    if payment.status == PaymentStatus.REVERSED:
        return {
            "payment_id": str(payment.id),
            "status": "reversed",
            "idempotent_replay": True,
            "loan_balance": str(loan.balance),
        }
    if payment.status != PaymentStatus.SUCCEEDED:
        raise HTTPException(status_code=409, detail="Only a successful payment can be reversed")

    latest = _last_payment_query(db, loan).first()
    if latest is None or latest.id != payment.id:
        raise HTTPException(status_code=409, detail="This is not the latest successful repayment")
    if payment.purpose != PaymentPurpose.LOAN_REPAYMENT or payment.payment_method != PaymentMethod.CASH:
        raise HTTPException(status_code=409, detail="Only cash loan repayments are supported; use reconciled refund procedures for electronic methods")
    if (payment.provider_payload or {}).get("early_settlement_id"):
        raise HTTPException(status_code=409, detail="Early-settlement payments require their dedicated reversal workflow")

    treasury_entry = (
        db.query(TreasuryEntry)
        .filter(
            TreasuryEntry.payment_transaction_id == payment.id,
            TreasuryEntry.company_id == company_id,
        )
        .with_for_update()
        .first()
    )
    if treasury_entry is None:
        raise HTTPException(status_code=409, detail="Missing treasury entry: payment requires manual reconciliation")
    if treasury_entry.is_voided:
        raise HTTPException(status_code=409, detail="Treasury entry was previously voided")

    # An approved carry-forward rewrites schedule dues. Reversing a payment
    # afterwards requires unwinding the rollover first, including its audit trail.
    # Do not silently reopen a settled-by-rollover installment.
    if (loan.calculation_breakdown or {}).get("installment_carry_forward_history"):
        raise HTTPException(
            status_code=409,
            detail="This loan has an approved installment carry-forward; reverse the restructuring before reversing payments",
        )

    before_balance = str(loan.balance)
    before_paid = str(loan.amount_paid)
    try:
        # Refuses reversal of allocations belonging to superseded renewal cycles.
        reverse_loan_payment(db, payment)
        void_treasury_entry(db, treasury_entry, user_id=user_id, reason=reason)
        payment.status = PaymentStatus.REVERSED
        accounting_reversal = record_reversal_accounting(db, payment)
        if accounting_reversal is None:
            raise HTTPException(status_code=409, detail="Original payment journal is missing; manual financial reconciliation required")
        payment.provider_payload = {
            **(payment.provider_payload or {}),
            "reversal": {
                "reason": reason,
                "reversed_by_user_id": str(user_id),
                "reversed_at": datetime.now(timezone.utc).isoformat(),
                "type": "last_cash_repayment",
            },
        }
        if loan.cdas_collection_enabled:
            plan = dict(loan.cdas_collection_plan or {})
            plan["autopilot_pending"] = {
                "reason": "cash_payment_reversed",
                "payment_id": str(payment.id),
                "requested_at": datetime.now(timezone.utc).isoformat(),
            }
            loan.cdas_collection_plan = plan
        db.add(AuditLog(
            user_id=user_id, company_id=company_id, branch_id=loan.branch_id,
            action="loan.repayment.reversed", table_name="payment_transactions",
            entity_type="payment_transaction", record_id=payment.id,
            actor_role=actor_role, severity="warning", status="success",
            description=f"Last cash repayment reversed: {payment.provider_reference}",
            before_data={"payment_status": "succeeded", "loan_balance": before_balance, "loan_paid": before_paid},
            after_data={"payment_status": "reversed", "loan_balance": str(loan.balance), "loan_paid": str(loan.amount_paid)},
            changed_fields=["status", "balance", "amount_paid", "instalment_allocations"],
            event_data={"reason": reason, "loan_id": str(loan.id), "payment_id": str(payment.id), "amount": str(payment.amount)},
        ))
        db.commit()
    except Exception:
        db.rollback()
        raise
    return {
        "payment_id": str(payment.id), "status": "reversed", "idempotent_replay": False,
        "loan_balance": str(loan.balance), "reversed_amount": str(payment.amount),
    }
