"""Loan list must remain scoped while avoiding the costly detail ORM loader."""
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from database.models.client_loan_company import ClientCompanyLoan
from database.models.enums import UserRole
from routers import loans


def _query():
    query = MagicMock()
    query.options.return_value = query
    query.filter.return_value = query
    query.order_by.return_value = query
    query.offset.return_value = query
    query.limit.return_value = query
    query.all.return_value = []
    return query


def test_company_loan_listing_uses_lightweight_loader_with_tenant_branch_scope(monkeypatch):
    query = _query()
    db = MagicMock()
    db.query.return_value = query
    company_id, branch_id = uuid4(), uuid4()
    context = SimpleNamespace(company_id=company_id, branch_id=branch_id, role=UserRole.LOAN_OFFICER)
    monkeypatch.setattr(loans, "resolve_tenant_context", lambda *_: context)
    monkeypatch.setattr(loans, "loan_query", lambda _: pytest.fail("Detail eager-loader must not run on list"))
    result = loans.list_loans(
        skip=0, limit=100, borrower_id=None,
        x_company_id=str(company_id), x_active_role="loan_officer",
        db=db, current_user=SimpleNamespace(role=UserRole.LOAN_OFFICER),
    )
    assert result == []
    db.query.assert_called_once_with(ClientCompanyLoan)
    assert query.options.call_count == 1
    assert len(query.options.call_args.args) == 2
    assert query.filter.call_count == 2  # company and branch
    query.offset.assert_called_once_with(0)
    query.limit.assert_called_once_with(100)


def test_superadmin_loan_listing_remains_unscoped(monkeypatch):
    query = _query()
    db = MagicMock()
    db.query.return_value = query
    monkeypatch.setattr(loans, "loan_query", lambda _: pytest.fail("Detail loader must not run"))
    assert loans.list_loans(
        skip=10, limit=30, borrower_id=None,
        x_company_id=None, x_active_role=None,
        db=db, current_user=SimpleNamespace(role=UserRole.SUPERADMIN),
    ) == []
    query.filter.assert_not_called()
    query.offset.assert_called_once_with(10)
    query.limit.assert_called_once_with(30)


def test_listing_invokes_focused_loader_not_detailed_loader(monkeypatch):
    from unittest.mock import Mock

    query = _query()
    db = MagicMock()
    focused = Mock(return_value=query)
    monkeypatch.setattr(loans, "loan_list_query", focused)
    monkeypatch.setattr(loans, "loan_query", lambda _: pytest.fail("Detail loader must not run"))
    loans.list_loans(
        skip=0, limit=10, borrower_id=None, x_company_id=None,
        x_active_role=None, db=db, current_user=SimpleNamespace(role=UserRole.SUPERADMIN),
    )
    focused.assert_called_once_with(db)
