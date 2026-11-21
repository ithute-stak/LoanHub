from types import SimpleNamespace as N

import pytest

from services.data_center_branch_projection import verified_branch_grant
from services.data_center_staff_projection import (
    require_staff_directory_management,
    safe_staff_row,
)


def context(role="company_owner", branch=None, company="c1"):
    return N(user=N(id="u1", is_active=True),
             staff=N(id="s1", user_id="u1", company_id=company,
                     branch_id=branch, role=role, is_active=True),
             company=N(is_active=True), company_id="c1",
             branch_id=branch, is_platform_admin=False)


def record(company="c1"):
    return N(id="s2", company_id=company, branch_id="b2",
             role="loan_officer", is_active=True,
             user=N(email="private@example.com", phone="SECRET"),
             employee_profile=N(salary=100000), is_primary=True)


def test_staff_projection_is_minimal_and_allowlisted():
    row = safe_staff_row(record(), verified_branch_grant(context()))
    assert row == {
        "id": "s2", "company_id": "c1", "branch_id": "b2",
        "role": "loan_officer", "status": "active",
    }


def test_admin_can_view_company_staff():
    grant = verified_branch_grant(context(role="company_admin"))
    require_staff_directory_management(grant)


@pytest.mark.parametrize("role,branch", [
    ("loan_officer", "b1"), ("branch_manager", "b1"),
    ("hr_manager", "b1"), ("finance_officer", "b1"),
])
def test_non_company_management_cannot_read_staff_directory(role, branch):
    grant = verified_branch_grant(context(role=role, branch=branch))
    with pytest.raises(PermissionError):
        require_staff_directory_management(grant)
    with pytest.raises(PermissionError):
        safe_staff_row(record(), grant)


def test_other_company_staff_rejected():
    with pytest.raises(PermissionError):
        safe_staff_row(record(company="c2"), verified_branch_grant(context()))


def test_inactive_staff_is_described_not_hidden():
    item = record()
    item.is_active = False
    assert safe_staff_row(item, verified_branch_grant(context()))["status"] == "inactive"


def test_platform_actor_cannot_use_staff_directory():
    actor = context()
    actor.is_platform_admin = True
    with pytest.raises(PermissionError):
        verified_branch_grant(actor)
