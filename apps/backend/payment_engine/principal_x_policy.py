"""Opt-in company payment-model policy, independent of LoanHub calculator.

This pure policy resolver does not alter company schema, loan origination,
existing agreements, or production collection behavior.
"""
from dataclasses import dataclass
from enum import Enum


class PaymentModel(str, Enum):
    EXISTING = "existing"
    PRINCIPAL_X = "principal_x"


@dataclass(frozen=True)
class PaymentModelPolicy:
    company_default: PaymentModel = PaymentModel.EXISTING
    allow_new_loans: bool = False
    enable_live_collections: bool = False


def select_payment_model(
    *,
    policy: PaymentModelPolicy,
    loan_model: PaymentModel | None = None,
    is_new_loan: bool,
) -> PaymentModel:
    """Fail closed: opt-in must be enabled for newly originated facilities.

    Existing loans remain on their established model even if a company
    changes its default. A separate, explicit migration process is required.
    """
    if not is_new_loan:
        return PaymentModel.EXISTING if loan_model is None else loan_model
    selected = loan_model if loan_model is not None else policy.company_default
    if selected == PaymentModel.PRINCIPAL_X and not policy.allow_new_loans:
        raise ValueError("Principal x% is not enabled for new loans")
    return selected


def can_post_principal_x_collections(policy: PaymentModelPolicy) -> bool:
    """Never infer production collection authorization from quote availability."""
    return policy.allow_new_loans and policy.enable_live_collections
