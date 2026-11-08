"""Fail-closed role, company and workstation rules for multi-operator bridge."""
from dataclasses import replace

import pytest

from database.models.enums import UserRole
from services.wacom_bridge_access_policy import BridgeAccess, BridgeFacts, decide_bridge_access


def facts(**overrides):
    base = BridgeFacts(
        authenticated=True,
        user_active=True,
        password_action_required=False,
        company_active=True,
        company_membership_active=True,
        role=UserRole.LOAN_OFFICER,
        workstation_enrolled=True,
        workstation_active=True,
        workstation_proof_valid=True,
        operator_assignment_active=True,
        lending_permission_active=True,
    )
    return replace(base, **overrides)


@pytest.mark.parametrize("role", [UserRole.BORROWER, UserRole.CUSTOMER_SUPPORT, None])
def test_borrowers_and_non_lending_users_never_enter_bridge(role):
    assert decide_bridge_access(facts(role=role)) == BridgeAccess.DENY


@pytest.mark.parametrize("role", [UserRole.COMPANY_OWNER, UserRole.COMPANY_ADMIN])
def test_owner_or_admin_can_configure_only_on_verified_workstation(role):
    assert decide_bridge_access(facts(role=role)) == BridgeAccess.COMPANY_SETUP
    assert decide_bridge_access(facts(role=role, workstation_proof_valid=False)) == BridgeAccess.DENY


@pytest.mark.parametrize("role", [UserRole.LOAN_OFFICER, UserRole.BRANCH_MANAGER, UserRole.CREDIT_ANALYST])
def test_authorized_lending_staff_can_use_shared_workstation(role):
    assert decide_bridge_access(facts(role=role)) == BridgeAccess.OPERATOR
    assert decide_bridge_access(facts(role=role, operator_assignment_active=False)) == BridgeAccess.DENY
    assert decide_bridge_access(facts(role=role, lending_permission_active=False)) == BridgeAccess.DENY


@pytest.mark.parametrize("name,value", [
    ("authenticated", False),
    ("user_active", False),
    ("password_action_required", True),
    ("company_active", False),
    ("company_membership_active", False),
    ("workstation_enrolled", False),
    ("workstation_active", False),
    ("workstation_proof_valid", False),
])
def test_access_denied_if_any_core_security_check_fails(name, value):
    assert decide_bridge_access(facts(**{name: value})) == BridgeAccess.DENY


def test_policy_never_returns_signing_permission():
    assert set(BridgeAccess) == {
        BridgeAccess.DENY, BridgeAccess.COMPANY_SETUP, BridgeAccess.OPERATOR
    }
