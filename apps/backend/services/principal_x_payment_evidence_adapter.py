"""Read-only adapter from real LoanHub payment rows to Principal x evidence.

A payment row alone cannot prove an authoritative refund link or lifetime
completeness. Never use this adapter to authorize collection posting.
"""
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.orm import Session

from database.models.enums import PaymentDirection, PaymentPurpose, PaymentStatus
from database.models.payment import PaymentTransaction
from payment_engine.principal_x_refund_reversal_preview import (
    PaymentEvidence, ReconciliationPreview, preview_reconciliation,
)


@dataclass(frozen=True)
class LoanHubPaymentAudit:
    preview: ReconciliationPreview
    payment_count: int
    unresolved_payment_ids: tuple[str, ...]
    complete: bool = False
    refund_payment_count: int = 0
    reversed_payment_count: int = 0
    nonfinal_refund_count: int = 0
    invalid_payment_amount_count: int = 0
    unsupported_currency_count: int = 0


def inspect_loanhub_payment_evidence(
    db: Session, *, company_id: UUID, loan_id: UUID,
) -> LoanHubPaymentAudit:
    """Inspect actual payment rows, preserving strict tenant and loan filters.

    No row is marked independently verified: provider settlement, cash
    receipts, legacy entries, and refund-to-original links are not certified
    by the payment table. Unknown/reversed records are explicit blockers.
    """
    if not isinstance(company_id, UUID) or not isinstance(loan_id, UUID):
        raise ValueError("Verified company and loan UUIDs required")
    rows = (
        db.query(PaymentTransaction)
        .filter(
            PaymentTransaction.company_id == company_id,
            PaymentTransaction.loan_id == loan_id,
        )
        .all()
    )
    evidence = []
    unresolved = []
    refund_count = 0
    reversal_count = 0
    nonfinal_refund_count = 0
    for row in rows:
        if row.purpose == PaymentPurpose.REFUND:
            refund_count += 1
            if row.status != PaymentStatus.SUCCEEDED or row.direction != PaymentDirection.OUTBOUND:
                nonfinal_refund_count += 1
        if row.status == PaymentStatus.REVERSED:
            reversal_count += 1
        identifier = str(row.id)
        if (
            row.purpose == PaymentPurpose.LOAN_REPAYMENT
            and row.direction == PaymentDirection.INBOUND
            and row.status == PaymentStatus.SUCCEEDED
        ):
            direction, status = "collection", "completed"
        elif (
            row.purpose == PaymentPurpose.REFUND
            and row.direction == PaymentDirection.OUTBOUND
            and row.status == PaymentStatus.SUCCEEDED
        ):
            direction, status = "refund", "completed"
            unresolved.append(identifier)  # no verified original-payment FK
        else:
            direction, status = "unresolved", str(row.status)
            unresolved.append(identifier)
        evidence.append(PaymentEvidence(
            payment_id=identifier,
            amount=row.amount,
            status=status,
            direction=direction,
            currency=row.currency,
            original_payment_id=None,
            verified=False,
        ))
    preview = preview_reconciliation(evidence)
    return LoanHubPaymentAudit(
        preview=preview,
        payment_count=len(rows),
        unresolved_payment_ids=tuple(unresolved),
        complete=False,
        refund_payment_count=refund_count,
        reversed_payment_count=reversal_count,
        nonfinal_refund_count=nonfinal_refund_count,
        invalid_payment_amount_count=sum(
            1 for reason in preview.unresolved if reason.endswith(":invalid_amount")
        ),
        unsupported_currency_count=sum(
            1 for reason in preview.unresolved if reason.endswith(":unsupported_currency")
        ),
    )
