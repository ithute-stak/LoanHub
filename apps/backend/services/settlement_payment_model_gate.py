"""Fail-closed model gate for the existing early-settlement payment workflow.

Principal x% has a separate read-only quote engine; it must not be posted
through the standard early-settlement service until a reconciled, authorized
Principal x% payment workflow is released.
"""
from fastapi import HTTPException
from sqlalchemy.orm import Session

from payment_engine.principal_x_policy import PaymentModel
from services.loan_payment_model_assignment_service import read_loan_payment_model


def require_standard_settlement_model(db: Session, *, loan) -> None:
    """Read the immutable, tenant-scoped assignment before quoting or paying."""
    try:
        assigned = read_loan_payment_model(
            db, loan_id=str(loan.id), company_id=str(loan.company_id),
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=409,
            detail="Loan payment-model assignment is invalid; settlement requires review",
        ) from exc
    if assigned != PaymentModel.EXISTING:
        raise HTTPException(
            status_code=409,
            detail=(
                "This loan uses Principal x%; the standard early-settlement "
                "quote and payment flow is not permitted. Use a verified "
                "Principal x% settlement workflow."
            ),
        )
