"""Individual CDAS attempt reservation contract tests (no live provider)."""
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from database.models.cdas_affordability_attempt import CdasAffordabilityAttempt
from services.cdas_affordability_attempts import (
    affordability_request_fingerprint,
    reserve_affordability_attempt,
    safe_attempt_status,
)


def test_fingerprint_is_canonical_and_scoped():
    company, borrower = uuid4(), uuid4()
    common = dict(company_id=company, borrower_id=borrower)
    assert affordability_request_fingerprint(
        **common, employee_number=" EMP-A ", installment=Decimal("100.0")
    ) == affordability_request_fingerprint(
        **common, employee_number="emp-a", installment=Decimal("100.00")
    )
    assert affordability_request_fingerprint(
        **common, employee_number="emp-a", installment=Decimal("100")
    ) != affordability_request_fingerprint(
        **common, employee_number="emp-a", installment=Decimal("101")
    )
    assert affordability_request_fingerprint(
        **common, employee_number="emp-a", installment=Decimal("100")
    ) != affordability_request_fingerprint(
        company_id=uuid4(), borrower_id=borrower,
        employee_number="emp-a", installment=Decimal("100")
    )


def test_schema_has_company_unique_key():
    constraints = CdasAffordabilityAttempt.__table__.constraints
    assert any(
        getattr(item, "name", None) == "uq_cdas_aff_attempt_company_key"
        for item in constraints
    )


def test_existing_attempt_does_not_create_another_provider_request():
    company_id, borrower_id = uuid4(), uuid4()
    expected = affordability_request_fingerprint(
        company_id=company_id, borrower_id=borrower_id,
        employee_number="E-1", installment=Decimal("100.00"),
    )
    prior = SimpleNamespace(id=uuid4(), request_fingerprint=expected,
                            state="reserved", assessment_record_id=None)
    class Query:
        def filter(self, *args):
            return self
        def first(self):
            return prior
    class DB:
        def query(self, model):
            return Query()
        def add(self, model):
            raise AssertionError("must not insert a duplicate")
        def commit(self):
            raise AssertionError("must not commit duplicate")
    attempt, created = reserve_affordability_attempt(
        DB(), company_id=company_id, actor_user_id=uuid4(),
        borrower_id=borrower_id, employee_number="E-1",
        installment=Decimal("100.00"),
        idempotency_key="test-attempt-key-001",
    )
    assert attempt is prior
    assert created is False
    assert safe_attempt_status(attempt)["may_retry_provider_request"] is False
    with pytest.raises(HTTPException) as raised:
        reserve_affordability_attempt(
            DB(), company_id=company_id, actor_user_id=uuid4(),
            borrower_id=borrower_id, employee_number="E-1",
            installment=Decimal("101.00"),
            idempotency_key="test-attempt-key-001",
        )
    assert raised.value.status_code == 409


def test_status_response_excludes_private_data():
    attempt = SimpleNamespace(id=uuid4(), state="unknown",
                              assessment_record_id=None, raw_provider_response="secret")
    result = safe_attempt_status(attempt)
    assert result["status"] == "unknown"
    assert result["requires_manual_review"] is True
    assert "raw_provider_response" not in result


@pytest.mark.parametrize("unresolved_state", ["reserved", "unknown"])
def test_new_idempotency_key_cannot_bypass_unresolved_fingerprint(unresolved_state):
    company_id, borrower_id = uuid4(), uuid4()
    unresolved = SimpleNamespace(
        id=uuid4(), state=unresolved_state, assessment_record_id=None,
    )
    class Query:
        def __init__(self, result):
            self.result = result
        def filter(self, *clauses):
            assert clauses
            return self
        def first(self):
            return self.result
    class DB:
        calls = 0
        def query(self, model):
            assert model is CdasAffordabilityAttempt
            self.calls += 1
            return Query(None if self.calls == 1 else unresolved)
        def add(self, item):
            raise AssertionError("Unresolved assessment must block new reservation")
        def commit(self):
            raise AssertionError("Unresolved assessment must not be committed")
    db = DB()
    with pytest.raises(HTTPException) as blocked:
        reserve_affordability_attempt(
            db, company_id=company_id, actor_user_id=uuid4(),
            borrower_id=borrower_id, employee_number="EMP-100",
            installment=Decimal("100.00"),
            consent_evidence_reference="CONSENT-001",
            idempotency_key="a-different-key-002",
        )
    assert blocked.value.status_code == 409
    assert blocked.value.detail["status"] == unresolved_state
    assert blocked.value.detail["may_retry_provider_request"] is False
    assert blocked.value.detail["requires_manual_review"] is True
    assert db.calls == 2


@pytest.mark.parametrize("collision", ["same_key", "same_fingerprint"])
def test_concurrent_reservation_integrity_collision_fails_closed(collision):
    """A raced insert must never authorize a second provider call."""
    from sqlalchemy.exc import IntegrityError

    company_id, borrower_id = uuid4(), uuid4()
    fingerprint = affordability_request_fingerprint(
        company_id=company_id, borrower_id=borrower_id,
        employee_number="EMP-100", installment=Decimal("100.00"),
        consent_evidence_reference="CONSENT-001",
    )
    other = SimpleNamespace(
        id=uuid4(), state="unknown", assessment_record_id=None,
        request_fingerprint=fingerprint,
    )
    class Query:
        def __init__(self, result):
            self.result = result
        def filter(self, *clauses):
            return self
        def first(self):
            return self.result
    class DB:
        def __init__(self):
            self.queries = 0
            self.rollbacks = 0
            self.commits = 0
        def query(self, model):
            assert model is CdasAffordabilityAttempt
            self.queries += 1
            if self.queries <= 2:
                return Query(None)
            if collision == "same_key":
                return Query(other if self.queries == 3 else None)
            return Query(None if self.queries == 3 else other)
        def add(self, item):
            assert isinstance(item, CdasAffordabilityAttempt)
        def commit(self):
            self.commits += 1
            raise IntegrityError("INSERT", {}, Exception("unique conflict"))
        def rollback(self):
            self.rollbacks += 1
        def refresh(self, item):
            raise AssertionError("Never refresh a conflicted reservation")
    db = DB()
    kwargs = dict(
        company_id=company_id, actor_user_id=uuid4(),
        borrower_id=borrower_id, employee_number="EMP-100",
        installment=Decimal("100.00"),
        consent_evidence_reference="CONSENT-001",
        idempotency_key="concurrent-collision-001",
    )
    if collision == "same_key":
        attempt, created = reserve_affordability_attempt(db, **kwargs)
        assert attempt is other
        assert created is False
    else:
        with pytest.raises(HTTPException) as blocked:
            reserve_affordability_attempt(db, **kwargs)
        assert blocked.value.status_code == 409
        assert blocked.value.detail["status"] == "unknown"
        assert blocked.value.detail["may_retry_provider_request"] is False
    assert db.commits == 1
    assert db.rollbacks == 1
