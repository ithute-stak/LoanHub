from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from database.models.enums import UserRole
from routers.cdas_api import CDAS_DOCUMENT_ROLES, _require_cdas_reader, _require_employee_scope


def _context(role: UserRole, *, branch_id=None):
    return SimpleNamespace(
        is_platform_admin=False,
        company_id=uuid4(),
        branch_id=branch_id,
        staff=SimpleNamespace(role=role),
        role=role,
    )


class _ProfileQuery:
    def __init__(self, result):
        self.result = result

    def filter(self, *_args, **_kwargs):
        return self

    def first(self):
        return self.result


def _db_with_profile(result):
    return SimpleNamespace(query=lambda *_models: _ProfileQuery(result))


def test_official_cdas_read_access_rejects_generic_company_roles():
    for role in (UserRole.CUSTOMER_SUPPORT, UserRole.HR_MANAGER, UserRole.IT_SUPPORT):
        with pytest.raises(HTTPException) as raised:
            _require_cdas_reader(_context(role))
        assert raised.value.status_code == 403


def test_official_cdas_read_access_allows_operational_and_oversight_roles():
    for role in (
        UserRole.LOAN_OFFICER,
        UserRole.CREDIT_ANALYST,
        UserRole.FINANCE_OFFICER,
        UserRole.COLLECTIONS_OFFICER,
        UserRole.COMPLIANCE_OFFICER,
        UserRole.AUDITOR,
        UserRole.RISK_MANAGER,
    ):
        _require_cdas_reader(_context(role))


def test_branch_scoped_employee_read_requires_branch_payroll_profile():
    context = _context(UserRole.LOAN_OFFICER, branch_id=uuid4())

    with pytest.raises(HTTPException) as raised:
        _require_employee_scope(_db_with_profile(None), context, "EMP001")

    assert raised.value.status_code == 403


def test_branch_scoped_employee_read_accepts_linked_branch_profile():
    context = _context(UserRole.LOAN_OFFICER, branch_id=uuid4())
    _require_employee_scope(_db_with_profile((uuid4(),)), context, "EMP001")


def test_company_wide_employee_read_does_not_require_branch_profile():
    context = _context(UserRole.COMPANY_ADMIN, branch_id=None)
    _require_employee_scope(object(), context, "EMP001")


def test_cdas_documents_are_more_restricted_than_general_reads():
    assert UserRole.LOAN_OFFICER not in CDAS_DOCUMENT_ROLES
    assert UserRole.CREDIT_ANALYST not in CDAS_DOCUMENT_ROLES
    assert UserRole.FINANCE_OFFICER in CDAS_DOCUMENT_ROLES
    assert UserRole.COLLECTIONS_OFFICER in CDAS_DOCUMENT_ROLES
    assert UserRole.AUDITOR in CDAS_DOCUMENT_ROLES
