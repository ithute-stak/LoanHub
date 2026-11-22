from types import SimpleNamespace as N

import pytest

from services.data_center_branch_projection import verified_branch_grant
from services.data_center_financial_projection import (
    require_payment_directory_management,
    safe_loan_row,
    safe_payment_row,
)


def grant(role="loan_officer", branch="b1"):
    context = N(
        user=N(id="u1", is_active=True),
        staff=N(user_id="u1", company_id="c1", branch_id=branch,
                role=role, is_active=True),
        company=N(is_active=True), company_id="c1",
        branch_id=branch, is_platform_admin=False,
    )
    return verified_branch_grant(context)


def loan(company="c1", branch="b1"):
    return N(id="loan-1", borrower_id="borrower-1", company_id=company,
             branch_id=branch, status="active", balance="900.00",
             principal_amount="1500.00", interest_rate="20", payment_transactions=[])


def payment(company="c1"):
    return N(id="payment-1", company_id=company, loan_id="loan-1",
             status="succeeded", amount="500.00", payer_phone="PRIVATE",
             idempotency_key="SECRET", provider_payload={"private": True})


def test_loan_projection_excludes_all_financial_amounts():
    assert safe_loan_row(loan(), grant()) == {
        "id": "loan-1", "company_id": "c1", "branch_id": "b1",
        "borrower_id": "borrower-1", "status": "active",
    }


@pytest.mark.parametrize("company,branch", [("c2", "b1"), ("c1", "b2"), ("c1", None)])
def test_loan_must_match_company_and_branch(company, branch):
    with pytest.raises(PermissionError):
        safe_loan_row(loan(company, branch), grant())


def test_company_owner_can_view_loans_across_branches():
    assert safe_loan_row(loan(branch="b2"), grant("company_owner", None))["branch_id"] == "b2"


def test_payment_status_only_no_amounts_or_provider_info():
    assert safe_payment_row(payment(), grant("company_admin", None)) == {
        "id": "payment-1", "company_id": "c1", "branch_id": None,
        "loan_id": "loan-1", "status": "succeeded",
    }


@pytest.mark.parametrize("role", ["branch_manager", "loan_officer", "finance_officer"])
def test_payment_directory_requires_company_management(role):
    with pytest.raises(PermissionError):
        require_payment_directory_management(grant(role, "b1"))


def test_payment_other_company_denied():
    with pytest.raises(PermissionError):
        safe_payment_row(payment("c2"), grant("company_owner", None))
