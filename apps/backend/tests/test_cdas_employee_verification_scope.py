from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from routers.cdas_employee_verification import _require_account_branch_scope


def test_branch_user_can_verify_borrower_in_same_branch():
    branch_id = uuid4()
    context = SimpleNamespace(branch_id=branch_id)
    account = SimpleNamespace(branch_id=branch_id)
    _require_account_branch_scope(context, account)


def test_branch_user_cannot_verify_borrower_in_other_branch():
    context = SimpleNamespace(branch_id=uuid4())
    account = SimpleNamespace(branch_id=uuid4())
    with pytest.raises(HTTPException) as raised:
        _require_account_branch_scope(context, account)
    assert raised.value.status_code == 403


def test_branch_user_cannot_verify_unassigned_borrower():
    context = SimpleNamespace(branch_id=uuid4())
    account = SimpleNamespace(branch_id=None)
    with pytest.raises(HTTPException) as raised:
        _require_account_branch_scope(context, account)
    assert raised.value.status_code == 403


def test_company_wide_user_can_verify_branch_or_unassigned_borrower():
    context = SimpleNamespace(branch_id=None)
    _require_account_branch_scope(context, SimpleNamespace(branch_id=uuid4()))
    _require_account_branch_scope(context, SimpleNamespace(branch_id=None))
