from __future__ import annotations

from contextlib import nullcontext
from types import SimpleNamespace
from uuid import uuid4

import pytest

from services import cdas_crash_safe_lifecycle as crash_safe
from services.cdas_deduction_lifecycle import CdasLifecycleError


class _FakeDb:
    def __init__(self, state):
        self.state = state
        self.commit_snapshots: list[tuple[bool, str | None, int | None]] = []
        self.no_autoflush = nullcontext()

    def commit(self):
        self.commit_snapshots.append(
            (
                bool(self.state.requires_reconciliation),
                self.state.last_error,
                self.state.last_request_type,
            )
        )


def test_arm_provider_write_persists_reconciliation_marker_before_local_disarm(monkeypatch):
    state = SimpleNamespace(
        requires_reconciliation=False,
        last_error=None,
        last_request_type=None,
    )
    db = _FakeDb(state)
    monkeypatch.setattr(
        crash_safe,
        "get_official_mandate",
        lambda _db, company_id, state_id: (state, SimpleNamespace()),
    )

    returned = crash_safe._arm_provider_write(
        db,
        company_id=uuid4(),
        state_id=uuid4(),
        request_type=4,
        description="Approval",
    )

    assert returned is state
    assert db.commit_snapshots[0][0] is True
    assert db.commit_snapshots[0][2] == 4
    assert "not yet been confirmed" in (db.commit_snapshots[0][1] or "")
    # The in-memory value is intentionally false so the existing lifecycle
    # implementation can proceed inside db.no_autoflush while PostgreSQL stays armed.
    assert state.requires_reconciliation is False


def test_arm_provider_write_rejects_already_uncertain_state(monkeypatch):
    state = SimpleNamespace(
        requires_reconciliation=True,
        last_error="uncertain",
        last_request_type=3,
    )
    db = _FakeDb(state)
    monkeypatch.setattr(
        crash_safe,
        "get_official_mandate",
        lambda _db, company_id, state_id: (state, SimpleNamespace()),
    )

    with pytest.raises(CdasLifecycleError) as raised:
        crash_safe._arm_provider_write(
            db,
            company_id=uuid4(),
            state_id=uuid4(),
            request_type=4,
            description="Approval",
        )

    assert raised.value.status_code == 409
    assert db.commit_snapshots == []


def test_restore_disarms_only_when_provider_result_was_not_marked_uncertain():
    state = SimpleNamespace(requires_reconciliation=False, last_error="validation marker")
    db = _FakeDb(state)
    crash_safe._restore_if_no_provider_result(db, state)
    assert state.last_error is None
    assert db.commit_snapshots[-1][0] is False

    uncertain = SimpleNamespace(requires_reconciliation=True, last_error="provider uncertain", last_request_type=5)
    uncertain_db = _FakeDb(uncertain)
    crash_safe._restore_if_no_provider_result(uncertain_db, uncertain)
    assert uncertain.last_error == "provider uncertain"
    assert uncertain_db.commit_snapshots == []
