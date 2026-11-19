"""Read-only, tenant-scoped lookup for a loan's assigned payment model.

No loan calculation, origination, or payment posting occurs here.
"""
from sqlalchemy.orm import Session

from database.models.loan_payment_model_assignment import LoanPaymentModelAssignmentRecord
from payment_engine.principal_x_loan_assignment import resolve_existing_loan_payment_model
from payment_engine.principal_x_policy import PaymentModel


def read_loan_payment_model(
    db: Session, *, loan_id: str, company_id: str,
) -> PaymentModel:
    if not loan_id or not str(loan_id).strip():
        raise ValueError("Loan identity is required")
    if not company_id or not str(company_id).strip():
        raise ValueError("Company identity is required")
    record = (
        db.query(LoanPaymentModelAssignmentRecord)
        .filter(
            LoanPaymentModelAssignmentRecord.loan_id == loan_id,
            LoanPaymentModelAssignmentRecord.company_id == company_id,
        )
        .one_or_none()
    )
    return resolve_existing_loan_payment_model(
        assigned_model=None if record is None else record.payment_model,
    )
