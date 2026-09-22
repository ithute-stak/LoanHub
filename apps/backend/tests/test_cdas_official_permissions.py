from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from database.models.enums import UserRole
from routers.cdas_api import _require_deduction_writer, _require_settlement_writer


def _context(role: UserRole):
    return SimpleNamespace(
        is_platform_admin=False,
        company_id=uuid4(),
        staff=SimpleNamespace(role=role),
    )


@pytest.mark.parametrize(
    "role",
    [
        UserRole.COMPANY_OWNER,
        UserRole.COMPANY_ADMIN,
        UserRole.BRANCH_MANAGER,
        UserRole.LOAN_OFFICER,
        UserRole.CREDIT_ANALYST,
        UserRole.FINANCE_OFFICER,
        UserRole.TREASURY_OFFICER,
        UserRole.COLLECTIONS_OFFICER,
        UserRole.AUDITOR,
        UserRole.COMPLIANCE_OFFICER,
    ],
)
def test_raw_cdas_deduction_writes_are_disabled_for_company_roles(role: UserRole):
    with pytest.raises(HTTPException) as raised:
        _require_deduction_writer(_context(role))
    assert raised.value.status_code == 410
    assert "loan-linked" in str(raised.value.detail).lower()


@pytest.mark.parametrize(
    "role",
    [
        UserRole.COMPANY_OWNER,
        UserRole.COMPANY_ADMIN,
        UserRole.LOAN_OFFICER,
        UserRole.FINANCE_OFFICER,
        UserRole.TREASURY_OFFICER,
        UserRole.COLLECTIONS_OFFICER,
        UserRole.AUDITOR,
        UserRole.COMPLIANCE_OFFICER,
        UserRole.CUSTOMER_SUPPORT,
    ],
)
def test_raw_cdas_settlement_is_disabled_for_company_roles(role: UserRole):
    with pytest.raises(HTTPException) as raised:
        _require_settlement_writer(_context(role))
    assert raised.value.status_code == 410
    assert "loan-linked" in str(raised.value.detail).lower()
