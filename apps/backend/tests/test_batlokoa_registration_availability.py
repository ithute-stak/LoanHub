"""Phase 90: new-only registration availability cannot enable writes."""
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from core.access_control import TenantContext
from database.models.enums import CompanyStatus, UserRole
from routers.batlokoa_registration_availability import (
    RegistrationAvailabilityRead,
    get_registration_availability,
    registration_availability_for_staff,
)


def context(*, role=UserRole.LOAN_OFFICER, active=True,
            branch_assigned=True, platform=False):
    user_id, company_id, branch_id = uuid4(), uuid4(), uuid4()
    staff = SimpleNamespace(
        company_id=company_id,
        user_id=user_id,
        role=role,
        is_active=active,
        branch_id=branch_id if branch_assigned else None,
    )
    return TenantContext(
        user=SimpleNamespace(id=user_id, is_active=True, role=role),
        staff=staff,
        company=SimpleNamespace(id=company_id, status=CompanyStatus.APPROVED, is_active=True),
        company_id=company_id,
        branch_id=branch_id if branch_assigned else None,
        is_platform_admin=platform,
    )


@pytest.mark.parametrize("role", [
    UserRole.LOAN_OFFICER, UserRole.BRANCH_MANAGER,
    UserRole.CREDIT_ANALYST, UserRole.COMPANY_OWNER,
    UserRole.COMPANY_ADMIN,
])
def test_lending_staff_get_only_fixed_disabled_status(role):
    result = registration_availability_for_staff(context(role=role))
    assert isinstance(result, RegistrationAvailabilityRead)
    assert result.new_only_registration_available is False
    assert result.can_submit_new_only_registration is False
    assert result.requires_identity_migration_approval is True
    assert result.requires_independent_release_approval is True
    assert result.reason_code == "NEW_ONLY_REGISTRATION_NOT_RELEASED"
    assert "company" not in result.model_dump_json()
    assert "branch" not in result.model_dump_json()
    assert "borrower" not in result.model_dump_json()
    assert get_registration_availability(context(role=role)) == result


@pytest.mark.parametrize("role", [
    UserRole.BORROWER, UserRole.AUDITOR,
    UserRole.FINANCE_OFFICER, UserRole.COLLECTIONS_OFFICER,
])
def test_non_lending_roles_are_not_granted_capability_information(role):
    with pytest.raises(HTTPException) as error:
        registration_availability_for_staff(context(role=role))
    assert error.value.status_code == 403


def test_revoked_or_branchless_membership_denied():
    for changed in (
        context(active=False),
        context(branch_assigned=False),
        context(platform=True),
    ):
        with pytest.raises(HTTPException) as error:
            registration_availability_for_staff(changed)
        assert error.value.status_code == 403


def test_cross_company_and_stale_staff_denied():
    wrong_company = context()
    object.__setattr__(wrong_company, "company_id", uuid4())
    with pytest.raises(HTTPException):
        registration_availability_for_staff(wrong_company)
    wrong_user = context()
    wrong_user.staff.user_id = uuid4()
    with pytest.raises(HTTPException):
        registration_availability_for_staff(wrong_user)


def test_route_has_no_body_parameter_or_registration_writer():
    from inspect import signature
    from routers.batlokoa_registration_availability import router

    route = next(
        r for r in router.routes
        if getattr(r, "path", "") == "/batlokoa/registration/availability"
    )
    assert route.methods == {"GET"}
    assert list(signature(get_registration_availability).parameters) == ["context"]
    assert list(signature(registration_availability_for_staff).parameters) == ["context"]


@pytest.mark.parametrize("change", [
    "missing_company",
    "cross_company",
    "pending_company",
    "inactive_company",
    "unverified_user",
    "wrong_branch",
    "missing_actor_uuid",
    "missing_company_uuid",
])
def test_tenant_scope_is_verified_before_exposing_preview(change):
    selected = context()
    if change == "missing_company":
        object.__setattr__(selected, "company", None)
    elif change == "cross_company":
        selected.company.id = uuid4()
    elif change == "pending_company":
        selected.company.status = CompanyStatus.PENDING
    elif change == "inactive_company":
        selected.company.is_active = False
    elif change == "unverified_user":
        selected.user.is_active = False
    elif change == "wrong_branch":
        selected.staff.branch_id = uuid4()
    elif change == "missing_actor_uuid":
        selected.user.id = "untrusted-actor"
    elif change == "missing_company_uuid":
        object.__setattr__(selected, "company_id", "untrusted-company")
    with pytest.raises(HTTPException) as error:
        registration_availability_for_staff(selected)
    assert error.value.status_code == 403


def test_company_management_can_preview_without_assigned_branch_but_cannot_submit():
    selected = context(role=UserRole.COMPANY_ADMIN, branch_assigned=False)
    result = registration_availability_for_staff(selected)
    assert result.can_submit_new_only_registration is False
    assert result.new_only_registration_available is False
