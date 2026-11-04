"""Registration must be pending; manager approval is separate; revoke fails closed."""
import base64
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException, Response

from routers import wacom_workstation_enrollment as route


class FakeDB:
    def __init__(self, row=None):
        self.row = row
        self.committed = 0
        self.rolled_back = 0
        self.added = []
    def add(self, item):
        self.added.append(item)
    def commit(self):
        self.committed += 1
    def rollback(self):
        self.rolled_back += 1
    def query(self, model):
        return self
    def filter(self, *args):
        return self
    def with_for_update(self):
        return self
    def one_or_none(self):
        return self.row


def context(company=None, operator=None):
    return SimpleNamespace(company_id=company or uuid4(), user=SimpleNamespace(id=operator or uuid4()))


def test_registers_pending_only_and_no_private_key(monkeypatch):
    allowed = []
    monkeypatch.setattr(route, "require_tenant_roles", lambda ctx, roles: allowed.append(roles))
    ctx = context()
    db = FakeDB()
    key = base64.b64encode(b"a" * 32).decode()
    resp = Response()
    out = route.register_wacom_workstation(
        payload=route.WorkstationRegistration(
            workstation_id=uuid4(), ed25519_public_key_base64=key,
        ),
        response=resp, db=db, context=ctx,
    )
    assert out["status"] == "pending"
    assert out["capture_enabled"] is False
    assert db.committed == 1 and len(db.added) == 1
    record = db.added[0]
    assert record.company_id == ctx.company_id
    assert record.operator_user_id == ctx.user.id
    assert record.ed25519_public_key == b"a" * 32
    assert record.status == "pending"
    assert resp.headers["Cache-Control"] == "no-store"
    assert allowed


@pytest.mark.parametrize("key", [
    "not base64", base64.b64encode(b"short").decode(),
    base64.b64encode(b"x"*32).decode().rstrip("="),
])
def test_rejects_malformed_public_keys(key):
    with pytest.raises(HTTPException):
        route._key(key)


def test_separate_manager_can_approve_but_registrant_cannot(monkeypatch):
    monkeypatch.setattr(route, "require_tenant_roles", lambda ctx, roles: None)
    owner = uuid4()
    ctx = context(operator=owner)
    row = SimpleNamespace(
        id=uuid4(), company_id=ctx.company_id, operator_user_id=owner,
        created_by=str(owner), approved_at=None, revoked_at=None,
        status="pending", updated_by=None,
    )
    db = FakeDB(row)
    with pytest.raises(HTTPException) as error:
        route.approve_wacom_workstation(row.id, Response(), db, ctx)
    assert error.value.status_code == 403
    assert db.committed == 0
    ctx.user.id = uuid4()
    out = route.approve_wacom_workstation(row.id, Response(), db, ctx)
    assert out["status"] == "active" and out["capture_enabled"] is False
    assert row.approved_at is not None and db.committed == 1
    with pytest.raises(HTTPException):
        route.approve_wacom_workstation(row.id, Response(), db, ctx)


def test_revoke_disables_active_workstation(monkeypatch):
    monkeypatch.setattr(route, "require_tenant_roles", lambda ctx, roles: None)
    ctx = context()
    row = SimpleNamespace(
        id=uuid4(), status="active", revoked_at=None, updated_by=None,
    )
    db = FakeDB(row)
    result = route.revoke_wacom_workstation(row.id, Response(), db, ctx)
    assert result["status"] == "revoked"
    assert result["capture_enabled"] is False
    assert row.revoked_at is not None
    with pytest.raises(HTTPException):
        route.revoke_wacom_workstation(row.id, Response(), db, ctx)


def test_api_routes_are_registered_and_only_preview():
    from api.v1.router import api_router
    paths = {r.path for r in api_router.routes}
    assert "/contract-signing/workstations" in paths
    assert "/contract-signing/workstations/{enrollment_id}/approve" in paths
    assert "/contract-signing/workstations/{enrollment_id}/revoke" in paths
    assert not any("/capture" in p for p in paths if "/workstations" in p)
