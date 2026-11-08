"""Proof-time device and operator eligibility checks must lock both rows.

Without these locks, management could revoke an assignment between the
eligibility read and the commit of a new five-minute session.
"""
from types import SimpleNamespace
from uuid import uuid4

from routers import wacom_bridge_device_proof as bridge
from database.models.wacom_workstation import WacomWorkstationEnrollment
from database.models.wacom_workstation_operator import WacomWorkstationOperator


class LockingQuery:
    def __init__(self, db, model):
        self.db = db
        self.model = model
        self.locked = False

    def filter(self, *args):
        return self

    def with_for_update(self):
        self.locked = True
        self.db.events.append(("locked", self.model))
        return self

    def one_or_none(self):
        if not self.locked:
            raise AssertionError("Unlocked workstation eligibility read")
        self.db.events.append(("read", self.model))
        if self.model is WacomWorkstationEnrollment:
            return self.db.enrollment
        if self.model is WacomWorkstationOperator:
            return self.db.assignment
        raise AssertionError("Unexpected model queried")


class DB:
    def __init__(self, *, pc=True, assignment=True):
        self.events = []
        self.enrollment = SimpleNamespace(workstation_id=uuid4()) if pc else None
        self.assignment = SimpleNamespace() if assignment else None

    def query(self, model):
        return LockingQuery(self, model)


def _ctx():
    return SimpleNamespace(company_id=uuid4(),user=SimpleNamespace(id=uuid4()))


def test_device_proof_acquires_enrollment_then_assignment_locks(monkeypatch):
    monkeypatch.setattr(bridge, "require_tenant_roles", lambda *_: None)
    db=DB()
    result=bridge._eligible_device(db,_ctx(),db.enrollment.workstation_id)
    assert result is db.enrollment
    assert db.events == [
        ("locked",WacomWorkstationEnrollment),
        ("read",WacomWorkstationEnrollment),
        ("locked",WacomWorkstationOperator),
        ("read",WacomWorkstationOperator),
    ]


def test_revoked_enrollment_does_not_proceed_to_assignment(monkeypatch):
    from fastapi import HTTPException
    import pytest
    monkeypatch.setattr(bridge, "require_tenant_roles", lambda *_: None)
    db=DB(pc=False)
    with pytest.raises(HTTPException) as exc:
        bridge._eligible_device(db,_ctx(),uuid4())
    assert exc.value.status_code==403
    assert db.events == [
        ("locked",WacomWorkstationEnrollment),
        ("read",WacomWorkstationEnrollment),
    ]


def test_unassigned_operator_fails_after_both_locked_reads(monkeypatch):
    from fastapi import HTTPException
    import pytest
    monkeypatch.setattr(bridge, "require_tenant_roles", lambda *_: None)
    db=DB(assignment=False)
    with pytest.raises(HTTPException) as exc:
        bridge._eligible_device(db,_ctx(),db.enrollment.workstation_id)
    assert exc.value.status_code==403
    assert [m for event,m in db.events if event=="locked"] == [
        WacomWorkstationEnrollment,WacomWorkstationOperator,
    ]
