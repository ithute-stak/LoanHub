import pytest

from payment_engine.principal_x_loan_assignment import (
    assign_new_loan_payment_model,
    resolve_existing_loan_payment_model,
)
from payment_engine.principal_x_policy import PaymentModel, PaymentModelPolicy


def test_new_loan_snapshots_company_default():
    policy = PaymentModelPolicy(PaymentModel.PRINCIPAL_X, True, False)
    assigned = assign_new_loan_payment_model(
        loan_id="loan-1", company_id="company-1", company_policy=policy,
    )
    assert assigned.model == PaymentModel.PRINCIPAL_X
    assert resolve_existing_loan_payment_model(
        assigned_model=assigned.model.value
    ) == PaymentModel.PRINCIPAL_X


def test_legacy_loan_never_inherits_new_company_default():
    assert resolve_existing_loan_payment_model(assigned_model=None) == PaymentModel.EXISTING


def test_new_loan_requires_company_opt_in():
    with pytest.raises(ValueError, match="not enabled"):
        assign_new_loan_payment_model(
            loan_id="loan-1", company_id="company-1",
            company_policy=PaymentModelPolicy(),
            requested_model=PaymentModel.PRINCIPAL_X,
        )


def test_unknown_persisted_assignment_fails_closed():
    with pytest.raises(ValueError, match="Unknown"):
        resolve_existing_loan_payment_model(assigned_model="unexpected")


@pytest.mark.parametrize("loan_id,company_id", [
    ("", "company-1"), ("loan-1", ""),
])
def test_assignment_requires_both_identities(loan_id, company_id):
    with pytest.raises(ValueError, match="identity"):
        assign_new_loan_payment_model(
            loan_id=loan_id, company_id=company_id,
            company_policy=PaymentModelPolicy(),
        )
