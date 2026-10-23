"""Phase 10: financial mutation integrity, ambiguity and tenant-boundary regression tests.

These tests never contact the CDAS provider.
"""
from __future__ import annotations

import asyncio
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest

from integrations.cdas import CdasError
from services import cdas_operation_ledger as ledger


def _operation():
    return SimpleNamespace(state="prepared", id=uuid4())


def _run(monkeypatch, provider_call):
    op = _operation()
    transitions = []
    monkeypatch.setattr(ledger, "begin_provider_operation", lambda *a, **kw: op)

    def transition(name):
        def apply(db, row, **kwargs):
            assert row is op
            row.state = name
            transitions.append(name)
        return apply

    for action, state in [
        ("mark_operation_submitting", "submitting"),
        ("mark_operation_acknowledged", "acknowledged"),
        ("mark_operation_rejected", "rejected"),
        ("mark_operation_unknown", "unknown_provider_state"),
    ]:
        monkeypatch.setattr(ledger, action, transition(state))

    async def invoke():
        return await ledger.execute_provider_operation(
            object(), company_id=uuid4(), branch_id=None, actor_user_id=uuid4(),
            environment="test", operation_type="deduction.lifecycle.4",
            request_snapshot={"EmployeeNo": "EMP-1", "DeductionID": 42},
            provider_call=provider_call,
        )

    return op, transitions, invoke


def test_provider_is_called_once_on_success(monkeypatch):
    calls = []
    async def provider_call():
        calls.append("write")
        return {"DeductionID": 42}

    op, transitions, invoke = _run(monkeypatch, provider_call)
    response, returned_op = asyncio.run(invoke())
    assert calls == ["write"]
    assert returned_op is op
    assert response["DeductionID"] == 42
    assert transitions == ["submitting", "acknowledged"]


def test_transport_timeout_never_retries_financial_write(monkeypatch):
    calls = []
    async def provider_call():
        calls.append("write")
        try:
            raise httpx.ReadTimeout("response lost")
        except httpx.RequestError as exc:
            raise CdasError(503, "CDAS timeout") from exc

    op, transitions, invoke = _run(monkeypatch, provider_call)
    with pytest.raises(ledger.CdasTrackedProviderError):
        asyncio.run(invoke())
    assert calls == ["write"]
    assert op.state == "unknown_provider_state"
    assert transitions == ["submitting", "unknown_provider_state"]


def test_explicit_provider_rejection_does_not_get_retried(monkeypatch):
    calls = []
    async def provider_call():
        calls.append("write")
        raise CdasError(400, "Invalid deduction amount")

    op, transitions, invoke = _run(monkeypatch, provider_call)
    with pytest.raises(ledger.CdasTrackedProviderError):
        asyncio.run(invoke())
    assert calls == ["write"]
    assert transitions == ["submitting", "rejected"]


def test_operation_fingerprint_prevents_cross_company_collision():
    request = {"EmployeeNo": "EMP-1", "DeductionID": 42}
    first = ledger.operation_fingerprint(
        company_id=uuid4(), environment="test",
        operation_type="deduction.lifecycle.4", request_snapshot=request,
    )
    second = ledger.operation_fingerprint(
        company_id=uuid4(), environment="test",
        operation_type="deduction.lifecycle.4", request_snapshot=request,
    )
    assert first != second
    assert len(first) == 64


def test_operation_endpoints_require_management_and_company_filter():
    from pathlib import Path
    source = (Path(__file__).resolve().parents[1] / "routers/cdas_api.py").read_text()
    for endpoint, next_endpoint in [
        ('@router.get("/operations")', '@router.get("/operations/{operation_id}")'),
        ('@router.get("/operations/{operation_id}")', '@router.post("/operations/{operation_id}/reconcile")'),
        ('@router.post("/operations/{operation_id}/reconcile")', '@router.'),
    ]:
        start = source.index(endpoint)
        end = source.find(next_endpoint, start + len(endpoint))
        snippet = source[start:end if end >= 0 else None]
        assert "_require_company_manager(context)" in snippet
        assert "CdasProviderOperation.company_id == context.company_id" in snippet
