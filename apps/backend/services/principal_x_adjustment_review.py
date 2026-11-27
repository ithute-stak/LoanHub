"""Read-only review of governance adjustments; not proof of external finality."""
from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from database.models.enums import PaymentDirection, PaymentPurpose, PaymentStatus
from database.models.governance_control import PaymentAdjustment
from database.models.payment import PaymentTransaction


@dataclass(frozen=True)
class AdjustmentReview:
    adjustment_count: int
    completed_count: int
    unresolved_count: int
    duplicate_completed_original_count: int
    excess_adjustment_original_count: int
    locally_consistent_count: int = 0
    inconsistent_completed_count: int = 0
    complete: bool = False


def _positive_money(value):
    amount = Decimal(str(value))
    if not amount.is_finite() or amount <= 0 or amount != amount.quantize(Decimal("0.01")):
        raise ValueError("Invalid adjustment amount")
    return amount


def review_adjustment_rows(*, payments, adjustments, company_id: UUID, loan_id: UUID):
    if not isinstance(company_id, UUID) or not isinstance(loan_id, UUID):
        raise ValueError("Verified scope required")
    originals = {}
    for payment in payments:
        if payment.company_id != company_id or payment.loan_id != loan_id or payment.id in originals:
            raise ValueError("Invalid original payment scope or identity")
        originals[payment.id] = payment
    completed = unresolved = locally_consistent = inconsistent = 0
    counts, totals = {}, {}
    seen = set()
    for row in adjustments:
        if row.company_id != company_id or row.payment_id not in originals:
            raise ValueError("Adjustment scope mismatch")
        original = originals[row.payment_id]
        if not row.id or row.id in seen:
            unresolved += 1
            continue
        seen.add(row.id)
        if row.status == "rejected":
            continue
        if row.status != "completed":
            unresolved += 1
            continue
        completed += 1
        counts[row.payment_id] = counts.get(row.payment_id, 0) + 1
        try:
            amount = _positive_money(row.amount)
            original_amount = _positive_money(original.amount)
        except (ValueError, TypeError, ArithmeticError):
            inconsistent += 1
            unresolved += 1
            continue
        totals[row.payment_id] = totals.get(row.payment_id, Decimal("0")) + amount
        if (
            row.adjustment_type not in {"refund", "reversal", "chargeback"}
            or row.currency != "LSL" or original.currency != row.currency
            or original.purpose != PaymentPurpose.LOAN_REPAYMENT
            or original.direction != PaymentDirection.INBOUND
            or original.status != PaymentStatus.REVERSED
            or amount != original_amount
            or not row.approval_request_id
            or not row.requested_by_user_id or not row.approved_by_user_id
            or row.requested_by_user_id == row.approved_by_user_id
            or row.approved_at is None or row.completed_at is None
            or row.completed_at < row.approved_at
        ):
            inconsistent += 1
            unresolved += 1
            continue
        locally_consistent += 1
        # Even consistent local records require independent confirmation.
        unresolved += 1
    excess = 0
    for key, total in totals.items():
        try:
            if total > _positive_money(originals[key].amount):
                excess += 1
        except (ValueError, TypeError, ArithmeticError):
            continue
    return AdjustmentReview(len(adjustments), completed, unresolved,
        sum(count > 1 for count in counts.values()), excess,
        locally_consistent_count=locally_consistent,
        inconsistent_completed_count=inconsistent)


def inspect_loan_adjustments(db, *, company_id: UUID, loan_id: UUID):
    if not isinstance(company_id, UUID) or not isinstance(loan_id, UUID):
        raise ValueError("Verified scope required")
    payments = db.query(PaymentTransaction).filter(
        PaymentTransaction.company_id == company_id,
        PaymentTransaction.loan_id == loan_id,
    ).all()
    adjustments = db.query(PaymentAdjustment).join(
        PaymentTransaction, PaymentAdjustment.payment_id == PaymentTransaction.id,
    ).filter(PaymentAdjustment.company_id == company_id,
             PaymentTransaction.company_id == company_id,
             PaymentTransaction.loan_id == loan_id).all()
    return review_adjustment_rows(payments=payments, adjustments=adjustments,
                                  company_id=company_id, loan_id=loan_id)
