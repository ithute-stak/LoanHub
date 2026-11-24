"""Immutable-at-origination Principal x% payment-model assignment.

A company default is resolved only at origination. Subsequent company policy
changes must not mutate a signed loan agreement or its payment-model choice.
"""
from dataclasses import dataclass

from payment_engine.principal_x_policy import (
    PaymentModel,
    PaymentModelPolicy,
    select_payment_model,
)


@dataclass(frozen=True)
class LoanPaymentModelAssignment:
    loan_id: str
    company_id: str
    model: PaymentModel


def assign_new_loan_payment_model(
    *, loan_id: str, company_id: str, company_policy: PaymentModelPolicy,
    requested_model: PaymentModel | None = None,
) -> LoanPaymentModelAssignment:
    if not loan_id or not str(loan_id).strip():
        raise ValueError("Loan identity is required")
    if not company_id or not str(company_id).strip():
        raise ValueError("Company identity is required")
    model = select_payment_model(
        policy=company_policy,
        loan_model=requested_model,
        is_new_loan=True,
    )
    return LoanPaymentModelAssignment(
        loan_id=str(loan_id), company_id=str(company_id), model=model,
    )


def resolve_existing_loan_payment_model(
    *, assigned_model: str | None,
) -> PaymentModel:
    """Absent assignment means legacy loan, never a new company default."""
    if assigned_model is None:
        return PaymentModel.EXISTING
    try:
        return PaymentModel(assigned_model)
    except ValueError as exc:
        raise ValueError("Unknown persisted loan payment model") from exc
