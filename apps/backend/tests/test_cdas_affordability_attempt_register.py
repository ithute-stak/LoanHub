"""Regression coverage for read-only company-scoped attempt recovery.

The recovery register never contacts CDAS and never exposes replay keys.
"""
from datetime import datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from pydantic import ValidationError
from routers import cdas_government_employees as mod


def test_billable_assessment_requires_idempotency_key():
    request = dict(
        borrower_id=uuid4(), employee_number="EMP-100",
        proposed_monthly_installment="100.00", authorisation_confirmed=True,
        consent_evidence_reference="CONSENT-EXAMPLE-001",
    )
    with pytest.raises(ValidationError):
        mod.RecordedGovernmentEmployeeAffordabilityRequest(**{
            key: value for key, value in request.items()
            if key != "consent_evidence_reference"
        }, idempotency_key="test-valid-key-001")
    with pytest.raises(ValidationError):
        mod.RecordedGovernmentEmployeeAffordabilityRequest(**request)
    with pytest.raises(ValidationError):
        mod.RecordedGovernmentEmployeeAffordabilityRequest(
            **request, idempotency_key="short",
        )


def test_read_only_attempt_register_scopes_company_and_redacts_key(monkeypatch):
    company_id = uuid4()
    actor_id = uuid4()
    borrower_id = uuid4()
    attempt = SimpleNamespace(
        id=uuid4(), borrower_id=borrower_id, idempotency_key="never-return-this-key",
        state="unknown", created_at=datetime(2026, 11, 19),
        assessment_record_id=None,
    )
    checked = []
    class Query:
        def filter(self, *clauses):
            checked.extend(clauses)
            return self
        def count(self):
            return 1
        def order_by(self, *args):
            return self
        def offset(self, number):
            assert number == 0
            return self
        def limit(self, number):
            assert number == 25
            return self
        def all(self):
            return [attempt]
    class DB:
        def query(self, model):
            assert model is mod.CdasAffordabilityAttempt
            return Query()
    monkeypatch.setattr(mod, "_require_company_manager", lambda context: None)
    context = SimpleNamespace(company_id=company_id, user=SimpleNamespace(id=actor_id))
    result = mod.list_government_affordability_attempts(
        page=1, page_size=25, context=context, db=DB(),
    )
    assert checked, "The attempt query must apply company scoping"
    assert result["total"] == 1
    assert result["items"][0]["status"] == "unknown"
    assert result["items"][0]["may_retry_provider_request"] is False
    assert "idempotency_key" not in result["items"][0]
    assert "never-return-this-key" not in repr(result)


@pytest.mark.asyncio
async def test_unauthorised_request_does_not_reserve_attempt(monkeypatch):
    from fastapi import HTTPException
    monkeypatch.setattr(mod, "_require_company_manager", lambda context: None)
    def forbidden_reserve(*args, **kwargs):
        raise AssertionError("No reservation before lawful authorisation")
    monkeypatch.setattr(mod, "reserve_affordability_attempt", forbidden_reserve)
    payload = mod.RecordedGovernmentEmployeeAffordabilityRequest(
        borrower_id=uuid4(), employee_number="EMP-100",
        proposed_monthly_installment="100.00",
        authorisation_confirmed=False,
        idempotency_key="test-unconfirmed-key-001",
        consent_evidence_reference="CONSENT-EXAMPLE-001",
    )
    with pytest.raises(HTTPException) as raised:
        await mod.create_government_affordability_record(
            payload=payload,
            context=SimpleNamespace(company_id=uuid4()),
            db=object(),
        )
    assert raised.value.status_code == 409


def test_consent_reference_is_bound_into_durable_request_fingerprint():
    from services.cdas_affordability_attempts import affordability_request_fingerprint
    company_id, borrower_id = uuid4(), uuid4()
    fixed = dict(
        company_id=company_id, borrower_id=borrower_id,
        employee_number="EMP-100", installment="100.00",
    )
    first = affordability_request_fingerprint(
        **fixed, consent_evidence_reference="CONSENT-ONE",
    )
    second = affordability_request_fingerprint(
        **fixed, consent_evidence_reference="CONSENT-TWO",
    )
    assert first != second


@pytest.mark.asyncio
async def test_whitespace_consent_reference_cannot_reserve_provider_attempt(monkeypatch):
    from fastapi import HTTPException
    monkeypatch.setattr(mod, "_require_company_manager", lambda context: None)
    def forbidden_reserve(*args, **kwargs):
        raise AssertionError("Whitespace evidence must be blocked before reservation")
    monkeypatch.setattr(mod, "reserve_affordability_attempt", forbidden_reserve)
    payload = mod.RecordedGovernmentEmployeeAffordabilityRequest(
        borrower_id=uuid4(), employee_number="EMP-100",
        proposed_monthly_installment="100.00", authorisation_confirmed=True,
        idempotency_key="test-whitespace-key-001",
        consent_evidence_reference="            ",
    )
    with pytest.raises(HTTPException) as raised:
        await mod.create_government_affordability_record(
            payload=payload,
            context=SimpleNamespace(company_id=uuid4()),
            db=object(),
        )
    assert raised.value.status_code == 422
