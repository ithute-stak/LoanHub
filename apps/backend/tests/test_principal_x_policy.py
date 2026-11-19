import pytest

from payment_engine.principal_x_policy import (
    PaymentModel, PaymentModelPolicy, can_post_principal_x_collections,
    select_payment_model,
)


def test_existing_loans_keep_original_model():
    policy = PaymentModelPolicy(PaymentModel.PRINCIPAL_X, True, False)
    assert select_payment_model(policy=policy, is_new_loan=False) == PaymentModel.EXISTING
    assert select_payment_model(
        policy=policy, is_new_loan=False, loan_model=PaymentModel.PRINCIPAL_X
    ) == PaymentModel.PRINCIPAL_X


def test_default_remains_existing_until_opt_in():
    assert select_payment_model(
        policy=PaymentModelPolicy(), is_new_loan=True
    ) == PaymentModel.EXISTING


def test_company_can_enable_new_loan_principal_x():
    policy = PaymentModelPolicy(PaymentModel.PRINCIPAL_X, True, False)
    assert select_payment_model(policy=policy, is_new_loan=True) == PaymentModel.PRINCIPAL_X
    assert not can_post_principal_x_collections(policy)


def test_disabled_company_cannot_select_principal_x():
    with pytest.raises(ValueError, match="not enabled"):
        select_payment_model(
            policy=PaymentModelPolicy(), is_new_loan=True,
            loan_model=PaymentModel.PRINCIPAL_X,
        )


def test_live_collections_need_separate_permission():
    assert not can_post_principal_x_collections(
        PaymentModelPolicy(PaymentModel.PRINCIPAL_X, True, False)
    )
    assert can_post_principal_x_collections(
        PaymentModelPolicy(PaymentModel.PRINCIPAL_X, True, True)
    )
