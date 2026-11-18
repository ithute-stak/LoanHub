"""Controlled payment-model assignment writes for newly originated loans.

Call only inside the authorized origination transaction, after the loan has
been created and before it is approved/disbursed. The caller must lock the
loan row and authorize the tenant. No commits occur in this service.
"""
from uuid import UUID

from sqlalchemy.orm import Session

from database.models.loan_payment_model_assignment import LoanPaymentModelAssignmentRecord
from payment_engine.principal_x_loan_assignment import assign_new_loan_payment_model
from payment_engine.principal_x_policy import PaymentModel, PaymentModelPolicy


def create_loan_payment_model_assignment(
    db: Session, *, loan, company_id: UUID, policy: PaymentModelPolicy,
    requested_model: PaymentModel | None = None,
) -> LoanPaymentModelAssignmentRecord:
    """Write-once assignment; do not silently replace or reassign existing loans."""
    if loan is None or getattr(loan, "id", None) is None:
        raise ValueError("Persisted loan is required")
    if str(getattr(loan, "company_id", "")) != str(company_id):
        raise ValueError("Loan belongs to a different company")
    if getattr(loan, "approved_at", None) is not None:
        raise ValueError("Approved loans cannot receive a new assignment")
    if getattr(loan, "disbursed_at", None) is not None:
        raise ValueError("Disbursed loans cannot receive a new assignment")
    existing = (
        db.query(LoanPaymentModelAssignmentRecord)
        .filter(LoanPaymentModelAssignmentRecord.loan_id == loan.id)
        .one_or_none()
    )
    if existing is not None:
        raise ValueError("Loan payment model has already been assigned")
    assignment = assign_new_loan_payment_model(
        loan_id=str(loan.id),
        company_id=str(company_id),
        company_policy=policy,
        requested_model=requested_model,
    )
    row = LoanPaymentModelAssignmentRecord(
        loan_id=loan.id,
        company_id=company_id,
        payment_model=assignment.model.value,
    )
    db.add(row)
    return row
