"""The directory must never leak product financial configuration."""
from types import SimpleNamespace as N

import pytest

from services.data_center_branch_projection import verified_branch_grant
from services.data_center_loan_product_projection import safe_loan_product_row


def context(*, role="loan_officer", branch="branch-1", company="company-1",
            user_active=True, membership_active=True):
    return N(
        user=N(id="user-1", is_active=user_active),
        staff=N(user_id="user-1", company_id=company, branch_id=branch,
                role=role, is_active=membership_active),
        company=N(is_active=True),
        company_id="company-1",
        branch_id=branch,
        is_platform_admin=False,
    )


def product(company="company-1", active=True):
    return N(
        id="product-1",
        company_id=company,
        name="Standard Loan",
        is_active=active,
        interest_rate_percent="20.000",
        min_amount="100.00",
        max_amount="5000.00",
        processing_fee="125.00",
        arrears_policy_override={"secret": "do not expose"},
        description="internal description",
    )


def test_loan_product_contains_only_directory_fields():
    row = safe_loan_product_row(product(), verified_branch_grant(context()))
    assert row == {
        "id": "product-1", "company_id": "company-1",
        "branch_id": "branch-1", "name": "Standard Loan", "status": "active",
    }


def test_company_admin_gets_company_scope():
    grant = verified_branch_grant(context(role="company_admin", branch=None))
    assert safe_loan_product_row(product(), grant)["branch_id"] is None


def test_inactive_product_visible_as_inactive():
    assert safe_loan_product_row(product(active=False),
                                 verified_branch_grant(context()))["status"] == "inactive"


def test_cross_company_product_rejected():
    with pytest.raises(PermissionError):
        safe_loan_product_row(product(company="other-company"),
                              verified_branch_grant(context()))


@pytest.mark.parametrize("kwargs", [
    {"company": "different-company"},
    {"user_active": False},
    {"membership_active": False},
    {"branch": None},
])
def test_invalid_membership_denied(kwargs):
    with pytest.raises(PermissionError):
        verified_branch_grant(context(**kwargs))


def test_missing_id_rejected():
    row = product()
    row.id = None
    with pytest.raises(PermissionError):
        safe_loan_product_row(row, verified_branch_grant(context()))


def test_invalid_name_rejected():
    row = product()
    row.name = None
    with pytest.raises(PermissionError):
        safe_loan_product_row(row, verified_branch_grant(context()))
