"""CDAS consent approval requires explicit independent review and verified bytes."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException
from routers import cdas_government_employees as module
from services.cdas_affordability_consent_policy import PURPOSE


class Query:
    def __init__(self, value):
        self.value = value
    def filter(self, *clauses):
        return self
    def with_for_update(self):
        return self
    def first(self):
        return self.value


class DB:
    def __init__(self, evidence, document, managed_file):
        self.evidence, self.document, self.managed_file = evidence, document, managed_file
        self.added = []
        self.commits = 0
    def query(self, model):
        if model is module.CdasAffordabilityConsentEvidence:
            return Query(self.evidence)
        if model is module.BorrowerDocument:
            return Query(self.document)
        if model is module.ManagedFile:
            return Query(self.managed_file)
        raise AssertionError("Unknown model")
    def add(self, item):
        self.added.append(item)
    def commit(self):
        self.commits += 1


def fixture():
    company, borrower, submitter, reviewer = (uuid4() for _ in range(4))
    record = SimpleNamespace(
        id=uuid4(), company_id=company, borrower_id=borrower,
        document_id=uuid4(), managed_file_id=uuid4(),
        employee_number="EMP-42", status="pending", purpose=PURPOSE,
        reference="CDAS-CONSENT-42", submitted_by_user_id=submitter,
        borrower_authorization_confirmed=True,
        document_sha256=None, verified_by_user_id=None, verified_at=None,
        expires_at=None,
    )
    db = DB(record, SimpleNamespace(id=record.document_id),
            SimpleNamespace(id=record.managed_file_id))
    context = SimpleNamespace(
        company_id=company, user=SimpleNamespace(id=reviewer),
        role=SimpleNamespace(value="company_owner"), branch_id=None,
    )
    return record, db, context


def payload(**overrides):
    args = dict(
        reviewed_document_sha256="a" * 64,
        document_reviewed=True, borrower_identity_checked=True,
        borrower_consent_checked=True, purpose_confirmed=True,
        reason="I reviewed the exact borrower consent document.",
        expires_at=datetime.now(timezone.utc) + timedelta(days=30),
    )
    args.update(overrides)
    return module.CdasConsentApprovalRequest(**args)


def test_independent_approval_reads_bytes_and_audits(monkeypatch):
    record, db, ctx = fixture()
    monkeypatch.setattr(module, "_require_company_manager", lambda context: None)
    checks = []
    def verify(**kwargs):
        checks.append(kwargs)
        return "a" * 64
    monkeypatch.setattr(module, "verify_managed_cdas_consent_bytes", verify)
    monkeypatch.setattr(module, "get_company_cdas_client",
                        lambda *a, **kw: (_ for _ in ()).throw(AssertionError("No provider call")))
    result = module.approve_cdas_consent_evidence(
        evidence_id=record.id, payload=payload(), context=ctx, db=db,
    )
    assert result["status"] == "approved"
    assert result["cdas_request_sent"] is False
    assert record.document_sha256 == "a" * 64
    assert record.verified_by_user_id == ctx.user.id
    assert len(checks) == 1
    assert checks[0]["borrower_id"] == record.borrower_id
    assert checks[0]["expected_digest"] == "a" * 64
    assert db.commits == 1
    assert db.added[0].event_data["managed_file_id"] == str(record.managed_file_id)


def test_submitter_cannot_approve(monkeypatch):
    record, db, ctx = fixture()
    ctx.user.id = record.submitted_by_user_id
    monkeypatch.setattr(module, "_require_company_manager", lambda context: None)
    monkeypatch.setattr(module, "verify_managed_cdas_consent_bytes",
                        lambda **kwargs: (_ for _ in ()).throw(AssertionError("No file read")))
    with pytest.raises(HTTPException) as denied:
        module.approve_cdas_consent_evidence(
            evidence_id=record.id, payload=payload(), context=ctx, db=db,
        )
    assert denied.value.status_code == 403
    assert db.commits == 0


@pytest.mark.parametrize("bad_payload", [
    {"document_reviewed": False}, {"borrower_identity_checked": False},
    {"borrower_consent_checked": False}, {"purpose_confirmed": False},
    {"expires_at": datetime.now(timezone.utc) + timedelta(days=91)},
    {"expires_at": datetime.now(timezone.utc) - timedelta(days=1)},
    {"expires_at": datetime.now() + timedelta(days=1)},
])
def test_unconfirmed_or_out_of_range_review_is_rejected(monkeypatch, bad_payload):
    record, db, ctx = fixture()
    monkeypatch.setattr(module, "_require_company_manager", lambda context: None)
    with pytest.raises(HTTPException):
        module.approve_cdas_consent_evidence(
            evidence_id=record.id, payload=payload(**bad_payload),
            context=ctx, db=db,
        )
    assert record.status == "pending"
    assert db.commits == 0


def test_changed_document_content_cannot_approve(monkeypatch):
    record, db, ctx = fixture()
    monkeypatch.setattr(module, "_require_company_manager", lambda context: None)
    def integrity_failure(**kwargs):
        raise HTTPException(409, "Digest does not match reviewed bytes")
    monkeypatch.setattr(module, "verify_managed_cdas_consent_bytes", integrity_failure)
    with pytest.raises(HTTPException) as denied:
        module.approve_cdas_consent_evidence(
            evidence_id=record.id, payload=payload(), context=ctx, db=db,
        )
    assert denied.value.status_code == 409
    assert record.status == "pending"
    assert db.commits == 0
