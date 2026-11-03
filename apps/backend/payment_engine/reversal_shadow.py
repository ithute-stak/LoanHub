"""Read-only shadow comparison of the existing cash reversal with payment_engine.

The existing LoanHub reversal remains authoritative. This function never
mutates the database; an inconsistency is only reported for investigation.
"""
from __future__ import annotations

import logging
from decimal import Decimal

from sqlalchemy.orm import Session

from database.models.accounting import JournalEntry
from database.models.enums import PaymentStatus
from database.models.repayment import PaymentAllocation, RepaymentInstallment
from database.models.loan_rollover_transfer import LoanRolloverTransfer
from payment_engine.reversal import (
    ReversalAllocation,
    ReversalRequest,
    preview_cash_reversal,
)

logger = logging.getLogger(__name__)


def inspect_cash_reversal_shadow(
    db: Session, *, loan, payment, treasury_entry, is_latest: bool
) -> dict:
    """Inspect database facts under the caller's existing loan/payment locks.

    Scope to the same loan and company. No writes or re-posts. The caller may
    run this only behind an explicitly enabled monitoring flag.
    """
    allocations = (
        db.query(PaymentAllocation, RepaymentInstallment)
        .join(RepaymentInstallment, RepaymentInstallment.id == PaymentAllocation.installment_id)
        .filter(
            PaymentAllocation.payment_id == payment.id,
            RepaymentInstallment.loan_id == loan.id,
        )
        .all()
    )
    journal_exists = (
        db.query(JournalEntry.id)
        .filter(
            JournalEntry.company_id == loan.company_id,
            JournalEntry.reference_type == "payment_transaction",
            JournalEntry.reference_id == str(payment.id),
            JournalEntry.status == "posted",
        )
        .first()
        is not None
    )
    rollover_exists = db.query(LoanRolloverTransfer.id).filter(
        LoanRolloverTransfer.parent_loan_id == loan.id
    ).first() is not None
    request = ReversalRequest(
        payment_id=str(payment.id),
        payment_status=payment.status.value,
        payment_method=payment.payment_method.value,
        payment_amount=Decimal(payment.amount),
        loan_amount_paid=Decimal(loan.amount_paid),
        loan_total_repayable=Decimal(loan.total_repayable),
        allocations=tuple(ReversalAllocation(
            installment_id=str(installment.id),
            original_amount=Decimal(allocation.amount),
            installment_current_paid=Decimal(installment.paid_amount),
            is_superseded=bool(getattr(installment, "is_superseded", False)),
        ) for allocation, installment in allocations),
        is_latest_repayment=is_latest,
        original_journal_exists=journal_exists,
        treasury_entry_exists=treasury_entry is not None,
        treasury_entry_voided=bool(treasury_entry.is_voided) if treasury_entry is not None else False,
        has_downstream_restructure=(
            bool((loan.calculation_breakdown or {}).get("installment_carry_forward_history"))
            or bool((loan.calculation_breakdown or {}).get("linked_rollover_out"))
            or rollover_exists
        ),
    )
    try:
        impact = preview_cash_reversal(request)
        return {
            "result": "eligible",
            "payment_id": str(payment.id),
            "expected_balance": str(impact.loan_balance_after),
            "expected_paid": str(impact.loan_paid_after),
        }
    except (ValueError, ArithmeticError) as exc:
        return {
            "result": "divergence",
            "payment_id": str(payment.id),
            "reason": str(exc),
        }
