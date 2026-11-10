"""Negative tests for signed/changed document review and operator isolation."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace as Row
from uuid import uuid4

import pytest
from fastapi import HTTPException

from routers import wacom_document_intents as routes


def test_original_pdf_requires_same_operator_and_workstation(monkeypatch):
    company, borrower, contract = uuid4(), uuid4(), uuid4()
    authorized_pc, actual_pc = uuid4(), uuid4()
    operator = uuid4()
    intent = Row(
        id=uuid4(), company_id=company, borrower_id=borrower,
        contract_id=contract, operator_user_id=operator,
        workstation_id=authorized_pc, status="prepared",
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=3),
    )
    monkeypatch.setattr(routes, "_session_device", lambda *args: actual_pc)
    monkeypatch.setattr(routes, "_current_intent", lambda *args, **kwargs: intent)
    ctx = Row(company_id=company, user=Row(id=operator))
    with pytest.raises(HTTPException) as exc:
        routes.preview_original_contract(intent.id, db=None, ctx=ctx)
    assert exc.value.status_code == 403
    assert "operator" in exc.value.detail.lower() or "review" in exc.value.detail.lower()
    # A different operator is independently rejected even on the right PC.
    monkeypatch.setattr(routes, "_session_device", lambda *args: authorized_pc)
    ctx.user.id = uuid4()
    with pytest.raises(HTTPException) as exc:
        routes.preview_original_contract(intent.id, db=None, ctx=ctx)
    assert exc.value.status_code == 403


def test_original_pdf_preview_never_mutates_execution_state():
    import inspect
    src = inspect.getsource(routes.preview_original_contract)
    for forbidden in (
        "db.commit(", "db.add(", "borrower_signed_at =",
        "status = 'signed'", 'status = "signed"',
        "consumed_at =", "executed_at =",
    ):
        assert forbidden not in src
    assert "verify_document_bytes(row.document_sha256, payload)" in src
    assert "X-Wacom-Signing-Authorized" in src
