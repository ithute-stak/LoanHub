"""Pad signing routes remain tenant-scoped and non-finalizing."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException
from database.models.enums import UserRole
from routers import contract_email_otp as pad


class SessionQuery:
    def __init__(self, record):
        self.record = record
        self.locked = False

    def filter(self, *args):
        return self

    def with_for_update(self, **kwargs):
        self.locked = True
        return self

    def one_or_none(self):
        return self.record


class FakeDb:
    def __init__(self, record):
        self.query_result = SessionQuery(record)
        self.commits = 0

    def query(self, model):
        return self.query_result

    def commit(self):
        self.commits += 1


def test_pad_cancel_locks_operator_session_and_never_signs(monkeypatch):
    company, contract, operator, session_id = (uuid4() for _ in range(4))
    row = SimpleNamespace(id=session_id, status="created")
    db = FakeDb(row)
    context = SimpleNamespace(company_id=company, user=SimpleNamespace(id=operator),
                              role=UserRole.COMPANY_OWNER)
    monkeypatch.setattr(pad, "require_tenant_roles", lambda *_: None)
    monkeypatch.setattr(pad, "_contract", lambda *_args, **_kwargs: SimpleNamespace(id=contract))
    result = pad.cancel_pad_signing_session(contract, session_id, db=db, context=context)
    assert result == {"session_id": str(session_id), "status": "cancelled", "capture_enabled": False}
    assert row.status == "cancelled"
    assert db.query_result.locked
    assert db.commits == 1


@pytest.mark.parametrize("state", ["cancelled", "expired", "captured", "completed"])
def test_pad_closed_or_captured_session_cannot_cancel(monkeypatch, state):
    row = SimpleNamespace(id=uuid4(), status=state)
    db = FakeDb(row)
    monkeypatch.setattr(pad, "require_tenant_roles", lambda *_: None)
    monkeypatch.setattr(pad, "_contract", lambda *_args, **_kwargs: object())
    with pytest.raises(HTTPException) as error:
        pad.cancel_pad_signing_session(uuid4(), row.id, db=db, context=SimpleNamespace(
            company_id=uuid4(), user=SimpleNamespace(id=uuid4()),
        ))
    assert error.value.status_code == 409
    assert db.commits == 0


def test_wacom_preview_never_enables_finalization():
    root = Path(__file__).resolve().parents[3]
    api = (root / "apps/frontend/components/contracts/contract-pad-preflight.tsx").read_text()
    assert "Prepare signing session" in api
    assert "Cancel session" in api
    assert "Hardware signing remains disabled" in api
    assert "onCapture=" not in api
