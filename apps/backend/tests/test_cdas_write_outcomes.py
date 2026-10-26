"""Financial-write ledger state transitions using a simulated provider only."""

from unittest.mock import MagicMock
from uuid import uuid4

import httpx
import pytest

from integrations.cdas import CdasError
from services import cdas_operation_ledger as ledger


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("outcome", "expected"),
    [("acknowledged", "acknowledged"), ("provider_rejected", "rejected"), ("timeout", "unknown")],
)
@pytest.mark.parametrize("operation_type", ["deduction.lifecycle.1", "deduction.lifecycle.3", "deduction.modify_active", "deduction.settle"])
async def test_tracked_write_calls_provider_once_and_records_outcome(monkeypatch, outcome, expected, operation_type):
    operation = MagicMock()
    states = []
    def begin(*args, **kwargs):
        assert kwargs["operation_type"] == operation_type
        return operation

    monkeypatch.setattr(ledger, "begin_provider_operation", begin)
    monkeypatch.setattr(ledger, "mark_operation_submitting", lambda *a, **kw: states.append("submitting"))
    monkeypatch.setattr(ledger, "mark_operation_acknowledged", lambda *a, **kw: states.append("acknowledged"))
    monkeypatch.setattr(ledger, "mark_operation_rejected", lambda *a, **kw: states.append("rejected"))
    monkeypatch.setattr(ledger, "mark_operation_unknown", lambda *a, **kw: states.append("unknown"))
    calls = 0

    async def provider():
        nonlocal calls
        calls += 1
        if outcome == "provider_rejected":
            raise CdasError(422, "Provider rejected request")
        if outcome == "timeout":
            try:
                raise httpx.ReadTimeout("simulated timeout")
            except httpx.RequestError as exc:
                raise CdasError(503, "CDAS service is unavailable") from exc
        return {"DeductionID": 123}

    arguments = dict(
        company_id=uuid4(), branch_id=None, actor_user_id=None,
        environment="test", operation_type=operation_type,
        request_snapshot={"EmployeeNo": "SIM-1", "DeductionAmount": "20.00"},
        provider_call=provider,
    )
    if outcome == "acknowledged":
        response, returned_operation = await ledger.execute_provider_operation(MagicMock(), **arguments)
        assert response == {"DeductionID": 123}
        assert returned_operation is operation
    else:
        with pytest.raises(ledger.CdasTrackedProviderError):
            await ledger.execute_provider_operation(MagicMock(), **arguments)

    assert calls == 1, "Never automatically replay a financial write"
    assert states == ["submitting", expected]
