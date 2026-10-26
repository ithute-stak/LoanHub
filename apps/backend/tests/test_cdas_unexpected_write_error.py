"""Provider write exceptions must not permit an unverified retry."""

from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from services import cdas_operation_ledger as ledger


@pytest.mark.asyncio
async def test_unexpected_provider_write_failure_marks_operation_unknown(monkeypatch):
    operation = MagicMock()
    events = []

    def begin(*args, **kwargs):
        events.append("begin")
        return operation

    def submitting(*args, **kwargs):
        events.append("submitting")

    def unknown(*args, **kwargs):
        events.append("unknown")
        assert args[1] is operation
        assert "verify provider state" in kwargs["error_message"]

    monkeypatch.setattr(ledger, "begin_provider_operation", begin)
    monkeypatch.setattr(ledger, "mark_operation_submitting", submitting)
    monkeypatch.setattr(ledger, "mark_operation_unknown", unknown)
    monkeypatch.setattr(ledger, "mark_operation_acknowledged", lambda *a, **k: pytest.fail("must not acknowledge"))

    calls = 0

    async def provider_call():
        nonlocal calls
        calls += 1
        raise RuntimeError("private provider failure detail")

    with pytest.raises(RuntimeError, match="private provider failure detail"):
        await ledger.execute_provider_operation(
            MagicMock(),
            company_id=uuid4(),
            branch_id=None,
            actor_user_id=None,
            environment="test",
            operation_type="registration",
            request_snapshot={"EmployeeNo": "TEST-1"},
            provider_call=provider_call,
        )

    assert events == ["begin", "submitting", "unknown"]
    assert calls == 1
