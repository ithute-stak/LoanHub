"""Saved-signature management must be scoped to the borrower and never sign."""
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from routers import contract_email_otp as api


class Query:
    def __init__(self, rows):
        self.rows = rows
        self.locked = False
        self.filtered = False
    def filter(self, *clauses):
        self.filtered = True
        return self
    def order_by(self, *args):
        return self
    def limit(self, count):
        assert count == 25
        return self
    def all(self):
        return self.rows
    def with_for_update(self):
        self.locked = True
        return self
    def one_or_none(self):
        return self.rows[0] if self.rows else None


class DB:
    def __init__(self, rows):
        self.query_obj = Query(rows)
        self.commits = 0
    def query(self, model):
        assert model is api.BorrowerSavedSignature
        return self.query_obj
    def commit(self):
        self.commits += 1


def setup(monkeypatch):
    tenant, borrower, contract_id, actor = [uuid4() for _ in range(4)]
    context = SimpleNamespace(company_id=tenant, user=SimpleNamespace(id=actor))
    contract = SimpleNamespace(id=contract_id, borrower_id=borrower)
    monkeypatch.setattr(api, "require_tenant_roles", lambda *_: None)
    monkeypatch.setattr(api, "_contract", lambda *args, **kwargs: contract)
    return contract, context


def test_listing_returns_metadata_only_never_key_or_pen_data(monkeypatch):
    contract, context = setup(monkeypatch)
    now = datetime.now(timezone.utc)
    saved = SimpleNamespace(
        id=uuid4(), status="active", capture_source="wacom_stu",
        created_at=now, reuse_opt_in_at=now, revoked_at=None,
        encrypted_storage_key="must-not-leak",
        evidence_sha256="a"*64,
    )
    db = DB([saved])
    result = api.list_borrower_saved_signatures(contract.id, db=db, context=context)
    assert result["automatic_reuse_enabled"] is False
    assert result["requires_fresh_contract_consent"] is True
    assert result["borrower_id"] == str(contract.borrower_id)
    assert len(result["signatures"]) == 1
    assert "must-not-leak" not in str(result)
    assert "evidence_sha256" not in str(result)
    assert db.commits == 0


def test_revoke_locks_and_marks_signature_without_signing(monkeypatch):
    contract, context = setup(monkeypatch)
    saved = SimpleNamespace(id=uuid4(), status="active", revoked_at=None, updated_by=None)
    db = DB([saved])
    result = api.revoke_borrower_saved_signature(contract.id, saved.id, db=db, context=context)
    assert result["future_reuse_allowed"] is False
    assert saved.status == "revoked"
    assert saved.revoked_at.tzinfo is not None
    assert saved.updated_by == str(context.user.id)
    assert db.query_obj.locked
    assert db.commits == 1


@pytest.mark.parametrize("status,exists,expected", [
    ("revoked", True, 409), ("active", False, 404),
])
def test_closed_and_missing_signature_are_rejected(monkeypatch, status, exists, expected):
    contract, context = setup(monkeypatch)
    saved = SimpleNamespace(id=uuid4(), status=status, revoked_at=None)
    db = DB([saved] if exists else [])
    with pytest.raises(HTTPException) as error:
        api.revoke_borrower_saved_signature(contract.id, saved.id, db=db, context=context)
    assert error.value.status_code == expected
    assert db.commits == 0
