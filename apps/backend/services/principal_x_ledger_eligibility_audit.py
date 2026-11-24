"""Read-only authoritative-ledger eligibility audit for Principal x.

This is NOT a reconciliation implementation. Existing payment records alone
cannot establish net lifetime collections because legacy, manual, refunds and
provider reversals may exist outside this table. Fail closed until all sources
have been reconciled and an audited adapter explicitly certifies completeness.
"""
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.orm import Session

from database.models.payment import PaymentTransaction


@dataclass(frozen=True)
class LedgerEligibilityAudit:
    company_id: UUID
    loan_id: UUID
    payment_rows: int
    incomplete_rows: int
    missing_provider_references: int
    can_certify_net_collected: bool
    reason: str


def audit_principal_x_ledger_eligibility(
    db: Session, *, company_id: UUID, loan_id: UUID,
) -> LedgerEligibilityAudit:
    """Inspect real payment rows without asserting they are complete."""
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
    incomplete = sum(
        1 for row in rows
        if getattr(getattr(row, "status", None), "value", getattr(row, "status", None))
        not in {"succeeded", "completed", "success"}
    )
    missing_refs = sum(1 for row in rows if not row.provider_reference)
    return LedgerEligibilityAudit(
        company_id=company_id,
        loan_id=loan_id,
        payment_rows=len(rows),
        incomplete_rows=incomplete,
        missing_provider_references=missing_refs,
        can_certify_net_collected=False,
        reason=(
            "PaymentTransaction history alone does not prove completeness "
            "of manual, legacy, provider, refund and reversal collections"
        ),
    )
