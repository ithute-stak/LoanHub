from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from database.models.enums import UserRole
from routers.cdas_lifecycle import (
    CDAS_SETTLEMENT_ROLES,
    _require_action_role,
    _require_branch_scope,
    _require_read_access,
)


def _context(role: UserRole, *, branch_id=None):
    return SimpleNamespace(
        is_platform_admin=False,
        company_id=uuid4(),
        branch_id=branch_id,
        staff=SimpleNamespace(role=role),
        role=role,
    )


def test_branch_scoped_user_cannot_access_other_branch_mandate():
    active_branch = uuid4()
    other_branch = uuid4()
    context = _context(UserRole.LOAN_OFFICER, branch_id=active_branch)
    mandate = SimpleNamespace(branch_id=other_branch)

    with pytest.raises(HTTPException) as raised:
        _require_branch_scope(context, mandate)

    assert raised.value.status_code == 403


def test_company_wide_user_can_access_any_branch_mandate():
    context = _context(UserRole.COMPANY_ADMIN, branch_id=None)
    _require_branch_scope(context, SimpleNamespace(branch_id=uuid4()))


def test_read_access_rejects_generic_non_financial_company_roles():
    for role in (UserRole.CUSTOMER_SUPPORT, UserRole.HR_MANAGER, UserRole.IT_SUPPORT):
        with pytest.raises(HTTPException) as raised:
            _require_read_access(_context(role))
        assert raised.value.status_code == 403


def test_read_access_allows_operational_and_audit_roles():
    for role in (
        UserRole.LOAN_OFFICER,
        UserRole.FINANCE_OFFICER,
        UserRole.COLLECTIONS_OFFICER,
        UserRole.CREDIT_ANALYST,
        UserRole.COMPLIANCE_OFFICER,
        UserRole.AUDITOR,
        UserRole.RISK_MANAGER,
    ):
        _require_read_access(_context(role))


def test_loan_officer_cannot_approve_or_activate():
    for request_type in (4, 5):
        with pytest.raises(HTTPException) as raised:
            _require_action_role(_context(UserRole.LOAN_OFFICER), request_type)
        assert raised.value.status_code == 403


def test_credit_analyst_can_review_but_not_approve():
    _require_action_role(_context(UserRole.CREDIT_ANALYST), 3)
    with pytest.raises(HTTPException) as raised:
        _require_action_role(_context(UserRole.CREDIT_ANALYST), 4)
    assert raised.value.status_code == 403


def test_branch_manager_can_review_approve_and_activate():
    context = _context(UserRole.BRANCH_MANAGER)
    for request_type in (3, 4, 5):
        _require_action_role(context, request_type)


def test_delete_is_owner_or_admin_only():
    with pytest.raises(HTTPException):
        _require_action_role(_context(UserRole.BRANCH_MANAGER), 9)
    _require_action_role(_context(UserRole.COMPANY_ADMIN), 9)


def test_settlement_excludes_ordinary_loan_officer_and_credit_analyst():
    assert UserRole.LOAN_OFFICER not in CDAS_SETTLEMENT_ROLES
    assert UserRole.CREDIT_ANALYST not in CDAS_SETTLEMENT_ROLES
    assert UserRole.FINANCE_OFFICER in CDAS_SETTLEMENT_ROLES
    assert UserRole.COLLECTIONS_OFFICER in CDAS_SETTLEMENT_ROLES
