from types import SimpleNamespace as N
import pytest
from services.data_center_branch_projection import verified_branch_grant, safe_branch_row


def ctx(role="loan_officer", branch="b1", active=True, membership=True, company="c1"):
    user = N(id="u1", is_active=active)
    staff = N(user_id="u1", company_id=company, branch_id=branch, role=role, is_active=membership)
    return N(user=user, staff=staff, company=N(is_active=True),
             company_id="c1", branch_id=branch, is_platform_admin=False)


def test_branch_summary_no_sensitive_fields():
    g = verified_branch_grant(ctx())
    row = N(id="b1", company_id="c1", name="North", is_active=True,
            phone="SECRET", address="SECRET")
    assert safe_branch_row(row, g) == {
        "id": "b1", "company_id": "c1", "branch_id": "b1",
        "name": "North", "status": "active",
    }


@pytest.mark.parametrize("bad", [
    ctx(company="c2"),
    ctx(active=False),
    ctx(membership=False),
    ctx(branch=None),
])
def test_invalid_memberships_denied(bad):
    with pytest.raises(PermissionError):
        verified_branch_grant(bad)


def test_staff_other_branch_denied():
    with pytest.raises(PermissionError):
        safe_branch_row(N(id="b2", company_id="c1"), verified_branch_grant(ctx()))


def test_company_owner_other_branch_allowed():
    grant = verified_branch_grant(ctx(role="company_owner"))
    assert safe_branch_row(N(id="b2", company_id="c1", name="South", is_active=False), grant)["status"] == "inactive"


def test_cross_company_row_denied():
    with pytest.raises(PermissionError):
        safe_branch_row(N(id="b1", company_id="c2"), verified_branch_grant(ctx(role="company_admin")))


def test_platform_denied():
    context = ctx()
    context.is_platform_admin = True
    with pytest.raises(PermissionError):
        verified_branch_grant(context)


def test_forged_user_denied():
    context = ctx()
    context.staff.user_id = "attacker"
    with pytest.raises(PermissionError):
        verified_branch_grant(context)


def test_branch_mismatch_denied():
    context = ctx()
    context.branch_id = "b2"
    with pytest.raises(PermissionError):
        verified_branch_grant(context)
