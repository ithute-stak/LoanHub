"""CDAS consent queue and denial decisions are tenant-scoped and never approve."""
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from routers import cdas_government_employees as module


class Query:
    def __init__(self, rows):
        self.rows = rows
        self.filtered = False
    def filter(self, *clauses):
        assert clauses
        self.filtered = True
        return self
    def count(self):
        return len(self.rows)
    def order_by(self, *clauses):
        return self
    def offset(self, offset):
        assert offset == 0
        return self
    def limit(self, limit):
        assert limit == 25
        return self
    def all(self):
        assert self.filtered
        return self.rows
    def with_for_update(self):
        return self
    def first(self):
        assert self.filtered
        return self.rows[0] if self.rows else None


class DB:
    def __init__(self, rows):
        self.rows = rows
        self.commits = 0
    def query(self, model):
        assert model is module.CdasAffordabilityConsentEvidence
        return Query(self.rows)
    def commit(self):
        self.commits += 1


def ctx(company=None, user=None):
    return SimpleNamespace(
        company_id=company or uuid4(),
        user=SimpleNamespace(id=user or uuid4()),
    )


def evidence(submitter):
    return SimpleNamespace(
        id=uuid4(), borrower_id=uuid4(), document_id=uuid4(),
        employee_number="EMP-123", reference="CONSENT-123",
        status="pending", submitted_by_user_id=submitter,
    )


def test_queue_is_company_scoped_and_read_only(monkeypatch):
    monkeypatch.setattr(module, "_require_company_manager", lambda ctx: None)
    submitter = uuid4()
    row = evidence(submitter)
    db = DB([row])
    response = module.list_cdas_consent_review_queue(
        page=1, page_size=25, context=ctx(), db=db,
    )
    assert response["total"] == 1
    assert response["items"][0]["status"] == "pending"
    assert response["items"][0]["cdas_request_authorized"] is False
    assert db.commits == 0


def test_independent_rejection_is_terminal_without_cdas(monkeypatch):
    monkeypatch.setattr(module, "_require_company_manager", lambda ctx: None)
    row = evidence(uuid4())
    db = DB([row])
    monkeypatch.setattr(module, "get_company_cdas_client",
                        lambda *args: (_ for _ in ()).throw(AssertionError("No CDAS")))
    response = module.reject_or_revoke_cdas_consent_evidence(
        evidence_id=row.id,
        payload=module.CdasConsentReviewDecision(
            decision="reject", reason="Document does not grant CDAS consent",
        ),
        context=ctx(), db=db,
    )
    assert response["status"] == "rejected"
    assert not response["cdas_request_authorized"]
    assert db.commits == 1
    with pytest.raises(HTTPException) as repeated:
        module.reject_or_revoke_cdas_consent_evidence(
            evidence_id=row.id,
            payload=module.CdasConsentReviewDecision(
                decision="reject", reason="Document does not grant CDAS consent",
            ),
            context=ctx(), db=db,
        )
    assert repeated.value.status_code == 409


def test_submitter_cannot_review_own_evidence(monkeypatch):
    monkeypatch.setattr(module, "_require_company_manager", lambda ctx: None)
    user = uuid4()
    row = evidence(user)
    db = DB([row])
    with pytest.raises(HTTPException) as denied:
        module.reject_or_revoke_cdas_consent_evidence(
            evidence_id=row.id,
            payload=module.CdasConsentReviewDecision(
                decision="reject", reason="Consent not given",
            ),
            context=ctx(user=user), db=db,
        )
    assert denied.value.status_code == 403
    assert db.commits == 0


def test_revoke_only_approved_and_approve_is_not_exposed(monkeypatch):
    monkeypatch.setattr(module, "_require_company_manager", lambda ctx: None)
    with pytest.raises(ValidationError):
        module.CdasConsentReviewDecision(
            decision="approve", reason="not a real review",
        )
    row = evidence(uuid4())
    db = DB([row])
    with pytest.raises(HTTPException) as denied:
        module.reject_or_revoke_cdas_consent_evidence(
            evidence_id=row.id,
            payload=module.CdasConsentReviewDecision(
                decision="revoke", reason="Borrower withdrew consent",
            ),
            context=ctx(), db=db,
        )
    assert denied.value.status_code == 409
    row.status = "approved"
    out = module.reject_or_revoke_cdas_consent_evidence(
        evidence_id=row.id,
        payload=module.CdasConsentReviewDecision(
            decision="revoke", reason="Borrower withdrew consent",
        ),
        context=ctx(), db=db,
    )
    assert out["status"] == "revoked"
    assert db.commits == 1
