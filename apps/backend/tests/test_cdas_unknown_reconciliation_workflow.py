"""Read-only resolution of uncertain CDAS provider operations (mock provider)."""
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from services import cdas_operation_ledger as ledger


@pytest.mark.asyncio
@pytest.mark.parametrize("provider_status,expected_confirmed", [(3, True), (1, False), (None, False)])
async def test_unknown_write_reconciles_only_on_matching_provider_state(monkeypatch, provider_status, expected_confirmed):
    operation = SimpleNamespace(
        state="unknown_provider_state", employee_no="TEST-9",
        operation_type="deduction.lifecycle.3",
        request_snapshot={"EmployeeNo": "TEST-9", "DeductionID": 100, "RequestType": 3},
        response_snapshot={},
    )
    events = []
    monkeypatch.setattr(ledger, "mark_operation_confirmed", lambda *a, **kw: events.append("confirmed"))
    monkeypatch.setattr(ledger, "mark_operation_requires_reconciliation", lambda *a, **kw: events.append("unresolved"))

    class ReadOnlyProvider:
        def __init__(self):
            self.calls = []

        async def view_own_deductions(self, employee_no, status):
            self.calls.append((employee_no, status))
            return [{"EmployeeNo": "TEST-9", "DeductionID": 100, "DeductionStatus": provider_status}]

        async def add_update_deduction(self, *_):
            pytest.fail("Reconciliation must never repeat a provider write")

    provider = ReadOnlyProvider()
    matched, returned = await ledger.reconcile_provider_operation(MagicMock(), operation=operation, client=provider)
    assert matched is expected_confirmed
    assert returned is operation
    assert events == ["confirmed" if expected_confirmed else "unresolved"]
    assert provider.calls == [("TEST-9", 3)]


@pytest.mark.asyncio
async def test_unresolved_operation_with_wrong_employee_cannot_confirm(monkeypatch):
    operation = SimpleNamespace(
        state="requires_reconciliation", employee_no="TEST-9",
        operation_type="deduction.lifecycle.3",
        request_snapshot={"EmployeeNo": "TEST-9", "DeductionID": 100, "RequestType": 3},
        response_snapshot={},
    )
    events = []
    monkeypatch.setattr(ledger, "mark_operation_confirmed", lambda *a, **kw: pytest.fail("wrong employee must not confirm"))
    monkeypatch.setattr(ledger, "mark_operation_requires_reconciliation", lambda *a, **kw: events.append("unresolved"))

    class Provider:
        async def view_own_deductions(self, employee_no, status):
            return [{"EmployeeNo": "OTHER", "DeductionID": 100, "DeductionStatus": 3}]

    matched, _ = await ledger.reconcile_provider_operation(MagicMock(), operation=operation, client=Provider())
    assert matched is False
    assert events == ["unresolved"]
