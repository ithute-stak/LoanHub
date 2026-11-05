"""Unit contract for the LoanHub-owned read-only borrower-company proof.

The dependency get_current_local_user verifies signed JWTs and current
session-version/JTI revocation. These tests validate the additional scope.
"""
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from database.models.enums import UserRole
from routers import auth


class StubQuery:
    def __init__(self, row):
        self.row = row
        self.filters = []
        self.join_calls = 0

    def join(self, *args):
        self.join_calls += 1
        return self

    def filter(self, *expressions):
        self.filters.extend(expressions)
        return self

    def first(self):
        return self.row


class StubDb:
    def __init__(self, row):
        self.query_obj = StubQuery(row)
        self.query_calls = 0

    def query(self, *_):
        self.query_calls += 1
        return self.query_obj


USER = uuid4()
BORROWER = uuid4()
COMPANY = uuid4()
OTHER_COMPANY = uuid4()


def local_user(**overrides):
    values = dict(
        id=USER, role=UserRole.BORROWER,
        is_active=True, is_verified=True, must_change_password=False,
    )
    values.update(overrides)
    return SimpleNamespace(**values)


def proof(monkeypatch, *, claims=None, user=None, row=(BORROWER,), tenant=COMPANY):
    claims = (
        dict(user_id=str(USER), token_type="access", session_jti=str(uuid4()))
        if claims is None else claims
    )
    monkeypatch.setattr(auth, "decode_token", lambda _: claims)
    db = StubDb(row)

    def invoke():
        return auth.borrower_company_context(
            company_id=tenant,
            current_user=local_user() if user is None else user,
            token="signed-local-session",
            db=db,
        )
    return invoke, db


def test_only_exact_active_verified_loan_company_is_returned(monkeypatch):
    invoke, db = proof(monkeypatch)
    result = invoke()
    assert result.user_id == USER and result.borrower_id == BORROWER
    assert result.company_id == COMPANY and result.role == UserRole.BORROWER
    assert result.session_active and result.account_active
    assert db.query_calls == 1 and db.query_obj.join_calls == 2
    filters = " ".join(str(value) for value in db.query_obj.filters)
    assert "borrowers.user_id" in filters
    assert "client_company_loan.company_id" in filters
    assert "loan_companies.is_active" in filters


@pytest.mark.parametrize("claims", [
    {"user_id": str(USER), "token_type": "refresh", "session_jti": str(uuid4())},
    {"user_id": str(USER), "token_type": "access", "session_jti": None},
    {"user_id": str(USER), "token_type": "access", "session_jti": ""},
    {"user_id": str(uuid4()), "token_type": "access", "session_jti": str(uuid4())},
    {"user_id": str(USER), "token_type": "access", "session_jti": str(uuid4()), "impersonated_by": "admin"},
])
def test_invalid_or_impersonation_session_fails_before_database(monkeypatch, claims):
    invoke, db = proof(monkeypatch, claims=claims)
    with pytest.raises(HTTPException) as exc:
        invoke()
    assert exc.value.status_code == 401 and db.query_calls == 0


@pytest.mark.parametrize("change", [
    {"role": UserRole.SUPERADMIN},
    {"role": UserRole.COMPANY_ADMIN},
    {"is_active": False},
    {"is_verified": False},
    {"must_change_password": True},
])
def test_nonborrower_or_unapproved_account_denied_without_database(monkeypatch, change):
    invoke, db = proof(monkeypatch, user=local_user(**change))
    with pytest.raises(HTTPException) as exc:
        invoke()
    assert exc.value.status_code == 403 and db.query_calls == 0


def test_no_loan_for_tenant_denies_mapping(monkeypatch):
    invoke, db = proof(monkeypatch, tenant=OTHER_COMPANY, row=None)
    with pytest.raises(HTTPException) as exc:
        invoke()
    assert exc.value.status_code == 404
    assert db.query_calls == 1


def test_read_only_implementation_has_no_session_commit_or_pii(monkeypatch):
    invoke, db = proof(monkeypatch)
    result = invoke()
    assert set(result.model_dump()) == {
        "user_id", "borrower_id", "company_id", "role",
        "session_active", "account_active",
    }
    assert not hasattr(db, "commit")
