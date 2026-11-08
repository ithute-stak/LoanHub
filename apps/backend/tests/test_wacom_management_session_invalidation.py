"""Revoking an employee or PC invalidates issued bridge sessions atomically."""
from datetime import datetime
from types import SimpleNamespace
from uuid import uuid4

from fastapi import Response

from routers import wacom_workstation_operators as operators
from routers import wacom_workstation_enrollment as enrollment
from database.models.wacom_bridge_session import WacomBridgeSession
from database.models.wacom_workstation_operator import WacomWorkstationOperator
from database.models.wacom_workstation import WacomWorkstationEnrollment


class Query:
    def __init__(self, db, model):
        self.db, self.model = db, model
    def filter(self, *expressions):
        self.db.filters[self.model] = expressions
        return self
    def with_for_update(self):
        return self
    def one_or_none(self):
        if self.model is WacomWorkstationOperator:
            return self.db.assignment
        if self.model is WacomWorkstationEnrollment:
            return self.db.enrollment
        return None
    def update(self, values, synchronize_session=False):
        assert self.model is WacomBridgeSession
        assert synchronize_session is False
        self.db.bulk_updates.append(values)
        return 2


class FakeDB:
    def __init__(self):
        self.assignment = SimpleNamespace(status="active", revoked_at=None, revoked_by=None)
        self.enrollment = SimpleNamespace(
            status="active", revoked_at=None, updated_by=None,
            workstation_id=uuid4(),
        )
        self.bulk_updates = []
        self.filters = {}
        self.commits = 0
    def query(self, model):
        return Query(self, model)
    def commit(self):
        # A commit without the matching session invalidation is unsafe.
        assert self.bulk_updates, "Management revoked access without invalidating tokens"
        self.commits += 1


def _ctx():
    actor = uuid4()
    return SimpleNamespace(
        company_id=uuid4(),
        user=SimpleNamespace(id=actor),
        branch_id=None,
        staff=SimpleNamespace(role="company_admin"),
    )


def test_revoke_employee_invalidates_sessions_before_commit(monkeypatch):
    db, ctx = FakeDB(), _ctx()
    pc, employee = uuid4(), uuid4()
    monkeypatch.setattr(operators, "require_tenant_roles", lambda *_: None)
    monkeypatch.setattr(operators, "_audit", lambda *_: None)
    result = operators.revoke_operator(pc, employee, Response(), db, ctx)
    assert result["status"] == "revoked"
    assert db.commits == 1
    assert isinstance(db.assignment.revoked_at, datetime)
    assert WacomBridgeSession.revoked_at in db.bulk_updates[0]
    sql = " AND ".join(str(x) for x in db.filters[WacomBridgeSession])
    assert "company_id" in sql and "workstation_id" in sql
    assert "employee_user_id" in sql and "revoked_at IS NULL" in sql


def test_revoke_pc_invalidates_all_operator_sessions_before_commit(monkeypatch):
    db, ctx = FakeDB(), _ctx()
    monkeypatch.setattr(enrollment, "require_tenant_roles", lambda *_: None)
    result = enrollment.revoke_wacom_workstation(uuid4(), Response(), db, ctx)
    assert result["status"] == "revoked"
    assert db.commits == 1
    assert isinstance(db.enrollment.revoked_at, datetime)
    assert WacomBridgeSession.revoked_at in db.bulk_updates[0]
    sql = " AND ".join(str(x) for x in db.filters[WacomBridgeSession])
    assert "company_id" in sql and "workstation_id" in sql
    assert "employee_user_id" not in sql  # ALL operators on this PC
    assert "revoked_at IS NULL" in sql
