"""No-live-provider regression tests for individual CDAS attempt replay/recovery.

These tests deliberately call the router directly with controlled doubles.
They assert provider calls NEVER occur on replay or read-only recovery.
"""
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from routers import cdas_government_employees as module


def _payload(borrower_id=None, key="assessment-replay-0001"):
    return module.RecordedGovernmentEmployeeAffordabilityRequest(
        borrower_id=borrower_id or uuid4(),
        employee_number="EMP-001", proposed_monthly_installment="250.00",
        authorisation_confirmed=True, idempotency_key=key,
        consent_evidence_reference="CONSENT-EXAMPLE-001",
    )


def _context(company_id=None):
    return SimpleNamespace(
        company_id=company_id or uuid4(), user=SimpleNamespace(id=uuid4()),
        role=SimpleNamespace(value="company_admin"), branch_id=None,
    )


@pytest.mark.asyncio
async def test_reserved_replay_never_contacts_cdas(monkeypatch):
    attempt = SimpleNamespace(id=uuid4(), state="reserved", assessment_record_id=None)
    monkeypatch.setattr(module, "_require_company_manager", lambda context: None)
    monkeypatch.setattr(module, "_require_approved_affordability_consent", lambda *args, **kwargs: None)
    monkeypatch.setattr(module, "reserve_affordability_attempt",
                        lambda db, **kwargs: (attempt, False))
    async def forbidden(*args, **kwargs):
        raise AssertionError("Second request must not contact CDAS")
    monkeypatch.setattr(module, "preview_government_employee_affordability", forbidden)
    with pytest.raises(HTTPException) as result:
        await module.create_government_affordability_record(
            payload=_payload(), context=_context(), db=object(),
        )
    assert result.value.status_code == 409
    assert result.value.detail["status"] == "reserved"
    assert result.value.detail["may_retry_provider_request"] is False


@pytest.mark.asyncio
async def test_completed_replay_returns_same_saved_report_without_cdas(monkeypatch):
    borrower = uuid4()
    record_id = uuid4()
    company = uuid4()
    attempt = SimpleNamespace(id=uuid4(), state="completed", assessment_record_id=record_id)
    record = SimpleNamespace(
        id=record_id, record_id=borrower,
        event_data={"snapshot": {
            "reference": "CDAS-AFF-EXISTING",
            "borrower_id": str(borrower),
            "employee_number": "EMP-001",
            "assessed_at": "2026-11-19T10:00:00+00:00",
            "decision": "pass",
            "proposed_installment": "250.00",
        }},
    )
    monkeypatch.setattr(module, "_require_company_manager", lambda context: None)
    monkeypatch.setattr(module, "_require_approved_affordability_consent", lambda *args, **kwargs: None)
    monkeypatch.setattr(module, "reserve_affordability_attempt",
                        lambda db, **kwargs: (attempt, False))
    class Query:
        def filter(self, *clauses):
            return self
        def first(self):
            return record
    def company_query(db, company_id):
        assert company_id == company
        return Query()
    monkeypatch.setattr(module, "_company_assessment_query", company_query)
    async def forbidden(*args, **kwargs):
        raise AssertionError("Completed replay must not contact CDAS")
    monkeypatch.setattr(module, "preview_government_employee_affordability", forbidden)
    payload = _payload(borrower)
    response = await module.create_government_affordability_record(
        payload=payload, context=_context(company), db=object(),
    )
    assert response["idempotent_replay"] is True
    assert response["record_id"] == str(record_id)
    assert response["reference"] == "CDAS-AFF-EXISTING"
    assert response["loan_approved"] is False


@pytest.mark.asyncio
async def test_provider_timeout_is_recorded_unknown_without_retry(monkeypatch):
    attempt = SimpleNamespace(id=uuid4(), state="reserved", assessment_record_id=None)
    monkeypatch.setattr(module, "_require_company_manager", lambda context: None)
    monkeypatch.setattr(module, "_require_approved_affordability_consent", lambda *args, **kwargs: None)
    monkeypatch.setattr(module, "reserve_affordability_attempt",
                        lambda db, **kwargs: (attempt, True))
    calls = 0
    async def timeout(*args, **kwargs):
        nonlocal calls
        calls += 1
        raise TimeoutError("Provider outcome uncertain")
    monkeypatch.setattr(module, "preview_government_employee_affordability", timeout)
    class DB:
        rollbacks = 0
        commits = 0
        def rollback(self):
            self.rollbacks += 1
        def commit(self):
            self.commits += 1
    db = DB()
    with pytest.raises(TimeoutError):
        await module.create_government_affordability_record(
            payload=_payload(), context=_context(), db=db,
        )
    assert calls == 1
    assert attempt.state == "unknown"
    assert db.rollbacks == 1
    assert db.commits == 1


def test_exact_saved_record_fails_closed_if_missing_or_corrupt(monkeypatch):
    monkeypatch.setattr(module, "_require_company_manager", lambda context: None)
    monkeypatch.setattr(module, "_require_approved_affordability_consent", lambda *args, **kwargs: None)
    company = uuid4()
    class Query:
        def __init__(self, found):
            self.found = found
        def filter(self, *args):
            return self
        def first(self):
            return self.found
    monkeypatch.setattr(module, "_company_assessment_query",
                        lambda db, company_id: Query(None))
    with pytest.raises(HTTPException) as missing:
        module.get_government_affordability_saved_record(
            record_id=uuid4(), context=_context(company), db=object(),
        )
    assert missing.value.status_code == 404
    corrupt = SimpleNamespace(id=uuid4(), record_id=uuid4(), event_data={"snapshot": {}})
    monkeypatch.setattr(module, "_company_assessment_query",
                        lambda db, company_id: Query(corrupt))
    with pytest.raises(HTTPException) as invalid:
        module.get_government_affordability_saved_record(
            record_id=corrupt.id, context=_context(company), db=object(),
        )
    assert invalid.value.status_code == 409
