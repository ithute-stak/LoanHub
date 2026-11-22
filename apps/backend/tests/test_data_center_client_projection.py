from types import SimpleNamespace as N

import pytest

from services.data_center_branch_projection import verified_branch_grant
from services.data_center_client_projection import safe_client_row


def context(role="loan_officer", branch="b1", company="c1"):
    return N(user=N(id="u1", is_active=True),
             staff=N(user_id="u1", company_id=company, branch_id=branch,
                     role=role, is_active=True),
             company=N(is_active=True), company_id="c1",
             branch_id=branch, is_platform_admin=False)


def record(company="c1", branch="b1"):
    return N(id="account-1", company_id=company, branch_id=branch,
             borrower_id="borrower-1", status="active",
             account_reference="PRIVATE", opening_fee_amount="1200",
             borrower=N(national_id="PRIVATE", phone="PRIVATE"),
             bank_account="PRIVATE")


def test_branch_account_directory_does_not_leak_sensitive_fields():
    grant = verified_branch_grant(context())
    assert safe_client_row(record(), grant) == {
        "id": "account-1", "company_id": "c1", "branch_id": "b1",
        "borrower_id": "borrower-1", "status": "active",
    }


def test_company_owner_can_view_other_branch():
    grant = verified_branch_grant(context(role="company_owner", branch=None))
    assert safe_client_row(record(branch="b2"), grant)["branch_id"] == "b2"


def test_regular_staff_cannot_view_other_branch():
    with pytest.raises(PermissionError):
        safe_client_row(record(branch="b2"), verified_branch_grant(context()))


def test_branch_bound_staff_cannot_view_unassigned_accounts():
    with pytest.raises(PermissionError):
        safe_client_row(record(branch=None), verified_branch_grant(context()))


def test_other_company_account_rejected():
    with pytest.raises(PermissionError):
        safe_client_row(record(company="c2"), verified_branch_grant(context(role="company_admin")))


def test_missing_borrower_identifier_rejected():
    item = record()
    item.borrower_id = None
    with pytest.raises(PermissionError):
        safe_client_row(item, verified_branch_grant(context()))


def test_platform_user_denied():
    actor = context()
    actor.is_platform_admin = True
    with pytest.raises(PermissionError):
        verified_branch_grant(actor)


def test_client_directory_requires_existing_lending_roles():
    from pathlib import Path
    source = (Path(__file__).resolve().parents[1] / "routers" / "data_center_directory.py").read_text()
    method = source.split('def client_directory(', 1)[1]
    assert "context.role not in LENDING_ROLES" in method
    assert 'status_code=403, detail="Client directory access denied"' in method
