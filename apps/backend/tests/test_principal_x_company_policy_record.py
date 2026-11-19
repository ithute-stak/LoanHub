import pytest

from payment_engine.principal_x_company_policy_record import parse_company_payment_policy
from payment_engine.principal_x_policy import PaymentModel


def test_missing_company_config_preserves_existing_model():
    record = parse_company_payment_policy(company_id="company-a", stored=None)
    assert record.as_policy().company_default == PaymentModel.EXISTING
    assert not record.as_policy().enable_live_collections


def test_explicit_company_opt_in():
    record = parse_company_payment_policy(
        company_id="company-a",
        stored={"default_model": "principal_x", "allow_new_loans": True},
    )
    assert record.as_policy().company_default == PaymentModel.PRINCIPAL_X
    assert not record.as_policy().enable_live_collections


@pytest.mark.parametrize("stored", [
    {"default_model": "unknown"},
    {"allow_new_loans": "true"},
    {"enable_live_collections": True},
    {"default_model": "existing", "allow_new_loans": True, "enable_live_collections": True},
    {"default_model": "principal_x", "allow_new_loans": True, "enable_live_collections": 1},
    {"unrecognized_flag": True},
])
def test_malformed_or_unsafe_company_config_rejected(stored):
    with pytest.raises(ValueError):
        parse_company_payment_policy(company_id="company-a", stored=stored)
