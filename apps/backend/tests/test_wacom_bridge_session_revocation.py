"""Server-side bridge logout prevents use of an unexpired device token."""
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException, Response

from routers.wacom_bridge_device_proof import revoke_bridge_session


class RowQuery:
    def __init__(self,row):
        self.row=row
    def filter(self,*args):
        return self
    def with_for_update(self):
        return self
    def one_or_none(self):
        return self.row


class FakeDB:
    def __init__(self,row):
        self.row=row
        self.commits=0
    def query(self,model):
        return RowQuery(self.row)
    def commit(self):
        self.commits+=1


def context():
    return SimpleNamespace(company_id=uuid4(),staff=object(),user=SimpleNamespace(id=uuid4()))


def test_session_revocation_sets_timestamp_and_is_idempotent():
    row=SimpleNamespace(revoked_at=None)
    db=FakeDB(row)
    token="wb1_"+"A"*43
    assert revoke_bridge_session(Response(),token,db,context())=={
        "revoked":True,"signing_authorized":False,
    }
    assert row.revoked_at is not None
    assert db.commits==1
    assert revoke_bridge_session(Response(),token,db,context())["revoked"]
    assert db.commits==1


@pytest.mark.parametrize("token",[None,"","bad","wb1_"+"*"*43])
def test_missing_or_malformed_token_is_denied(token):
    with pytest.raises(HTTPException) as exc:
        revoke_bridge_session(Response(),token,FakeDB(None),context())
    assert exc.value.status_code==403


def test_unknown_token_cannot_revoke_other_operator_session():
    with pytest.raises(HTTPException) as exc:
        revoke_bridge_session(Response(),"wb1_"+"A"*43,FakeDB(None),context())
    assert exc.value.status_code==403


def test_server_revocation_route_registered():
    from api.v1.router import api_router
    assert any(r.path=="/wacom-bridge/sessions/revoke" and "POST" in r.methods
               for r in api_router.routes)
