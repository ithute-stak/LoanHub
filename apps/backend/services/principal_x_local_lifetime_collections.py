"""Unified local lifetime collection diagnostic; never a posting authorization."""
from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from database.models.enums import PaymentDirection, PaymentPurpose, PaymentStatus
from database.models.payment import PaymentTransaction


@dataclass(frozen=True)
class LocalLifetimeCollections:
    recorded_successful_repayments: Decimal
    historical_opening_credit: Decimal | None
    recorded_credit_before_adjustments: Decimal | None
    recorded_loan_paid: Decimal
    unexplained_difference: Decimal | None
    unresolved_payment_count: int
    authoritative_net_collected: None = None
    reconciled: bool = False


def _money(value):
    amount = Decimal(str(value))
    if not amount.is_finite() or amount < 0 or amount != amount.quantize(Decimal("0.01")):
        raise ValueError("Invalid monetary evidence")
    return amount


def compare_local_lifetime_collections(*, company_id: UUID, loan_id: UUID,
                                       payments, recorded_paid, historical_opening_credit):
    """One contribution per payment identity; supporting sources are not additive.

    A missing historical opening is unknown, not zero. Gross recorded successes
    are not authoritative net lifetime collections, particularly after refunds.
    """
    if not isinstance(company_id, UUID) or not isinstance(loan_id, UUID):
        raise ValueError("Verified scope required")
    paid = _money(recorded_paid)
    opening = None if historical_opening_credit is None else _money(historical_opening_credit)
    seen = set()
    gross = Decimal("0.00")
    unresolved = 0
    for row in payments:
        if row.company_id != company_id or row.loan_id != loan_id:
            raise ValueError("Payment scope mismatch")
        if not row.id or row.id in seen:
            unresolved += 1
            continue
        seen.add(row.id)
        if (row.purpose != PaymentPurpose.LOAN_REPAYMENT
            or row.direction != PaymentDirection.INBOUND
            or row.status != PaymentStatus.SUCCEEDED):
            unresolved += 1
            continue
        try:
            amount = _money(row.amount)
            if amount <= 0 or row.currency != "LSL" or row.completed_at is None:
                raise ValueError("Incomplete repayment evidence")
        except (ValueError, TypeError, ArithmeticError):
            unresolved += 1
            continue
        gross += amount
    combined = None if opening is None else opening + gross
    return LocalLifetimeCollections(
        gross, opening, combined, paid,
        None if combined is None else paid - combined, unresolved,
    )


def inspect_local_lifetime_collections(db, *, company_id: UUID, loan_id: UUID,
                                       recorded_paid, historical_opening_credit):
    if not isinstance(company_id, UUID) or not isinstance(loan_id, UUID):
        raise ValueError("Verified scope required")
    payments = db.query(PaymentTransaction).filter(
        PaymentTransaction.company_id == company_id,
        PaymentTransaction.loan_id == loan_id,
    ).all()
    return compare_local_lifetime_collections(
        company_id=company_id, loan_id=loan_id, payments=payments,
        recorded_paid=recorded_paid, historical_opening_credit=historical_opening_credit,
    )
