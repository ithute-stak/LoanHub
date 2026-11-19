"""Persistent CDAS bulk draft API: no provider call or execution path."""
from types import SimpleNamespace
from uuid import uuid4
from decimal import Decimal
from unittest.mock import MagicMock
import pytest
from fastapi import HTTPException
from routers import cdas_government_employees as mod


def payload():
    return mod.CreateBulkAffordabilityDraft(
        idempotency_key="batch-repeatable-key-001",
        consent_evidence_reference="CONSENT-DOC-001",
        employees=[mod.BulkAffordabilitySelection(
            borrower_id=uuid4(), employee_number="EMP-100",
            proposed_monthly_installment=Decimal("100.00"),
        )],
    )


def company_context():
    return SimpleNamespace(company_id=uuid4(), staff=object(), is_platform_admin=False,
                           user=SimpleNamespace(id=uuid4()))


def test_create_draft_never_executes_provider(monkeypatch):
    context = company_context()
    monkeypatch.setattr(mod, "_require_company_manager", lambda _: None)
    monkeypatch.setattr(mod, "_bulk_candidate_status", lambda *args, **kwargs: "ready_for_live_verification")
    created = []
    class Q:
        def __init__(self, model):
            self.model = model
        def filter(self, *args):
            return self
        def first(self):
            if self.model is mod.OriginationPolicy:
                return SimpleNamespace(is_active=True)
            return None
    class DB:
        def query(self, model):
            return Q(model)
        def add(self, value):
            created.append(value)
        def flush(self):
            for value in created:
                if getattr(value, "id", None) is None:
                    value.id = uuid4()
        def commit(self):
            pass
    result = mod.create_government_affordability_draft_batch(
        payload=payload(), context=context, db=DB(),
    )
    assert result["status"] == "draft"
    assert result["execution_enabled"] is False
    assert len(created) == 2
    assert created[0].consent_evidence_reference == "CONSENT-DOC-001"
    assert created[1].attempt_count == 0


def test_cancel_rejects_non_draft():
    with pytest.raises(ValueError):
        mod.transition_batch("running", "cancelled")


def test_idempotency_conflicting_consent_reference_rejected(monkeypatch):
    context = company_context()
    request = payload()
    monkeypatch.setattr(mod, "_require_company_manager", lambda _: None)
    existing = SimpleNamespace(
        id=uuid4(), status="draft",
        request_fingerprint=mod.batch_fingerprint(request.employees),
        consent_evidence_reference="SOME-OTHER-CONSENT",
    )
    class Q:
        def filter(self, *args):
            return self
        def first(self):
            return existing
    class DB:
        def query(self, model):
            return Q()
    with pytest.raises(HTTPException) as raised:
        mod.create_government_affordability_draft_batch(
            payload=request, context=context, db=DB(),
        )
    assert raised.value.status_code == 409
