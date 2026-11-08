"""Wacom bridge sessions are scoped, short lived, and recheck revocation."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from services import wacom_bridge_sessions as service


class FakeQuery:
    def __init__(self, row):
        self.row = row
    def filter(self,*args):
        return self
    def one_or_none(self):
        return self.row
    def first(self):
        return self.row


class FakeDB:
    def __init__(self, session=None, pc=True, assignment=True):
        self.session = session
        self.pc = pc
        self.assignment = assignment
        self.added = []
    def add(self,row):
        self.added.append(row)
    def query(self, model):
        if model is service.WacomBridgeSession:
            return FakeQuery(self.session)
        if model is service.WacomWorkstationEnrollment.id:
            return FakeQuery(self.pc and (uuid4(),) or None)
        if model is service.WacomWorkstationOperator.id:
            return FakeQuery(self.assignment and (uuid4(),) or None)
        raise AssertionError("Unexpected database query")


def context():
    return SimpleNamespace(
        company_id=uuid4(), user=SimpleNamespace(id=uuid4()),
        staff=SimpleNamespace(is_active=True),
    )


def test_issued_session_token_is_opaque_and_only_digest_stored():
    db=FakeDB()
    ctx=context()
    token, row=service.issue_bridge_session(db,context=ctx,workstation_id=uuid4())
    assert token.startswith("wb1_")
    assert len(token)==47
    assert token.encode() not in bytes(row.token_sha256)
    assert row.employee_user_id==ctx.user.id
    assert row.company_id==ctx.company_id
    assert db.added==[row]


@pytest.mark.parametrize("token", [None,"", "invalid", "wb1_bad", "wb1_"+"*"*43])
def test_bad_session_token_denied(token):
    with pytest.raises(HTTPException) as exc:
        service.authorize_bridge_session(FakeDB(),context=context(),token=token)
    assert exc.value.status_code==403


@pytest.mark.parametrize("pc,assignment",[(False,True),(True,False),(False,False)])
def test_revoked_pc_or_assignment_denies_session(pc,assignment):
    ctx=context()
    token="wb1_"+"a"*43
    db=FakeDB(session=SimpleNamespace(workstation_id=uuid4()),pc=pc,assignment=assignment)
    with pytest.raises(HTTPException) as exc:
        service.authorize_bridge_session(db,context=ctx,token=token)
    assert exc.value.status_code==403


def test_current_assignment_and_pc_pass():
    ctx=context()
    token="wb1_"+"a"*43
    db=FakeDB(session=SimpleNamespace(workstation_id=uuid4()))
    service.authorize_bridge_session(db,context=ctx,token=token)


def test_opt_in_enforcement_defaults_off(monkeypatch):
    monkeypatch.delenv("LOANHUB_WACOM_REQUIRE_BRIDGE_SESSION",raising=False)
    assert service.bridge_enforcement_enabled() is False
    monkeypatch.setenv("LOANHUB_WACOM_REQUIRE_BRIDGE_SESSION","1")
    assert service.bridge_enforcement_enabled() is True
    monkeypatch.setenv("LOANHUB_WACOM_REQUIRE_BRIDGE_SESSION","false")
    assert service.bridge_enforcement_enabled() is False
