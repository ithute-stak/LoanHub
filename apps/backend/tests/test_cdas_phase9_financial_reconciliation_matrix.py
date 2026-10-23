"""Offline financial lifecycle reconciliation matrix: no writes to the CDAS provider."""
from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from services import cdas_operation_ledger as ledger


def operation(kind: str, request_type: int | None = None):
    request = {
        "EmployeeNo": "EMP-1",
        "DeductionID": 42,
        "ItemCode": "LOAN",
        "ReferenceNo": "REF-42",
        "DeductionAmount": "500.00",
        "PrincipalAmount": "1500.00",
        "TotalInstallment": 3,
    }
    if request_type is not None:
        request["RequestType"] = request_type
    return SimpleNamespace(
        state="requires_reconciliation",
        operation_type=kind,
        employee_no="EMP-1",
        deduction_id=42,
        request_snapshot=request,
        response_snapshot={},
    )


class ReadOnlyProvider:
    def __init__(self, rows):
        self.rows = rows
        self.calls = []

    async def view_own_deductions(self, employee, status):
        self.calls.append(("view", employee, status))
        return self.rows

    async def get_active_and_approved_deduction(self, employee):
        self.calls.append(("active", employee))
        return self.rows

    def __getattr__(self, name):
        if name in {"add_update_deduction", "modify_active_deduction", "settle_deduction"}:
            raise AssertionError("CDAS writes are forbidden during reconciliation")
        raise AttributeError(name)


def reconcile(monkeypatch, op, provider):
    events = []

    def confirmed(db, row, **kwargs):
        events.append(("confirmed", kwargs))
        row.state = "confirmed"

    def unresolved(db, row, **kwargs):
        events.append(("unresolved", kwargs))
        row.state = "requires_reconciliation"

    monkeypatch.setattr(ledger, "mark_operation_confirmed", confirmed)
    monkeypatch.setattr(ledger, "mark_operation_requires_reconciliation", unresolved)
    matched, row = asyncio.run(ledger.reconcile_provider_operation(
        object(), operation=op, client=provider,
    ))
    return matched, row, events


@pytest.mark.parametrize("request_type", [1, 3, 4, 6, 10])
def test_lifecycle_reconciliation_checks_identity_and_actual_status(monkeypatch, request_type):
    op = operation(f"deduction.lifecycle.{request_type}", request_type)
    provider = ReadOnlyProvider([
        {"EmployeeNo": "EMP-2", "DeductionID": 42, "DeductionStatus": request_type},
        {"EmployeeNo": "EMP-1", "DeductionID": 99, "DeductionStatus": request_type},
        {"EmployeeNo": "EMP-1", "DeductionID": 42, "DeductionStatus": 999},
        {"EmployeeNo": "EMP-1", "DeductionID": 42, "DeductionStatus": request_type},
    ])
    matched, row, events = reconcile(monkeypatch, op, provider)
    assert matched is True
    assert row.state == "confirmed"
    assert provider.calls == [("view", "EMP-1", request_type)]
    assert events[0][0] == "confirmed"
    assert events[0][1]["response_snapshot"]["reconciliation"]["DeductionStatus"] == request_type


@pytest.mark.parametrize("kind,status", [
    ("deduction.lifecycle.4", 4),
    ("deduction.settle", 7),
])
def test_wrong_provider_status_remains_unresolved(monkeypatch, kind, status):
    op = operation(kind, 4 if status == 4 else None)
    provider = ReadOnlyProvider([{
        "EmployeeNo": "EMP-1", "DeductionID": 42, "DeductionStatus": 3,
    }])
    matched, row, events = reconcile(monkeypatch, op, provider)
    assert matched is False
    assert row.state == "requires_reconciliation"
    assert provider.calls == [("view", "EMP-1", status)]
    assert events[0][0] == "unresolved"


def test_settlement_requires_status_7(monkeypatch):
    op = operation("deduction.settle")
    provider = ReadOnlyProvider([{
        "EmployeeNo": "EMP-1", "DeductionID": 42, "DeductionStatus": 7,
    }])
    matched, row, events = reconcile(monkeypatch, op, provider)
    assert matched is True
    assert row.state == "confirmed"
    assert provider.calls == [("view", "EMP-1", 7)]


@pytest.mark.parametrize("amount,principal,installments,expected", [
    ("500.00", "1500.00", 3, True),
    ("600.00", "1500.00", 3, False),
    ("500.00", "1600.00", 3, False),
    ("500.00", "1500.00", 4, False),
])
def test_modification_readback_checks_financial_terms(monkeypatch, amount, principal, installments, expected):
    op = operation("deduction.modify_active")
    provider = ReadOnlyProvider({
        "EmployeeNo": "EMP-1",
        "DeductionID": 42,
        "DeductionAmount": amount,
        "PrincipalAmount": principal,
        "TotalInstallment": installments,
    })
    matched, row, events = reconcile(monkeypatch, op, provider)
    assert matched is expected
    assert row.state == ("confirmed" if expected else "requires_reconciliation")
    assert provider.calls == [("active", "EMP-1")]
    assert events[0][0] == ("confirmed" if expected else "unresolved")
