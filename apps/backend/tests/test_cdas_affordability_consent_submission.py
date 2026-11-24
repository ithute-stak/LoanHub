"""Pending CDAS consent evidence must not grant permission to contact CDAS."""
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException
from routers import cdas_government_employees as module


def request(*, borrower, document, authorized=True):
    return module.PendingCdasConsentEvidenceRequest(
        borrower_id=borrower, document_id=document, managed_file_id=uuid4(), employee_number="EMP-100",
        reference="CONSENT-TEST-001", borrower_authorization_confirmed=authorized,
    )


def context(company):
    return SimpleNamespace(company_id=company, user=SimpleNamespace(id=uuid4()))


class Query:
    def __init__(self, db, model):
        self.db, self.model = db, model

    def filter(self, *args):
        return self

    def all(self):
        return self.db.employees.get(self.model, [])

    def first(self):
        if self.model is module.BorrowerDocument:
            return self.db.document
        if self.model is module.ManagedFile:
            return self.db.managed_file
        if self.model is module.CdasAffordabilityConsentEvidence:
            return self.db.existing
        return None


class DB:
    def __init__(self, borrower, document):
        self.employees = {
            module.CDASPayrollProfile: [SimpleNamespace(borrower_id=borrower)],
            module.BorrowerEmploymentProfile: [],
        }
        self.document = SimpleNamespace(id=document)
        self.managed_file = SimpleNamespace(id=uuid4())
        self.existing = None
        self.added = []
        self.commits = 0

    def query(self, model):
        return Query(self, model)

    def add(self, item):
        self.added.append(item)

    def commit(self):
        self.commits += 1

    def refresh(self, item):
        item.id = uuid4()


def test_pending_submission_never_approves_or_contacts_cdas(monkeypatch):
    borrower, document, company = uuid4(), uuid4(), uuid4()
    db = DB(borrower, document)
    monkeypatch.setattr(module, "_require_company_manager", lambda ctx: None)
    monkeypatch.setattr(module, "verify_managed_cdas_consent_bytes", lambda **kw: "a" * 64)
    def provider_forbidden(*args, **kwargs):
        raise AssertionError("Submitting evidence must not invoke CDAS")
    monkeypatch.setattr(module, "get_company_cdas_client", provider_forbidden)
    result = module.submit_pending_cdas_consent_evidence(
        payload=request(borrower=borrower, document=document),
        context=context(company), db=db,
    )
    assert result["status"] == "pending"
    assert result["verified"] is False
    assert result["cdas_request_authorized"] is False
    assert db.commits == 1
    assert len(db.added) == 1
    evidence = db.added[0]
    assert evidence.status == "pending"
    assert evidence.company_id == company
    assert evidence.borrower_id == borrower
    assert evidence.document_id == document
    assert evidence.managed_file_id == db.managed_file.id
    assert evidence.verified_at is None
    assert evidence.verified_by_user_id is None
    assert evidence.document_sha256 is None


def test_pending_submission_rejects_missing_authorization_before_writes(monkeypatch):
    borrower, document, company = uuid4(), uuid4(), uuid4()
    db = DB(borrower, document)
    monkeypatch.setattr(module, "_require_company_manager", lambda ctx: None)
    with pytest.raises(HTTPException) as raised:
        module.submit_pending_cdas_consent_evidence(
            payload=request(borrower=borrower, document=document, authorized=False),
            context=context(company), db=db,
        )
    assert raised.value.status_code == 409
    assert db.commits == 0
    assert not db.added


def test_pending_submission_blocks_ambiguous_borrower_or_missing_document(monkeypatch):
    borrower, document, company = uuid4(), uuid4(), uuid4()
    db = DB(borrower, document)
    monkeypatch.setattr(module, "_require_company_manager", lambda ctx: None)
    db.employees[module.BorrowerEmploymentProfile] = [SimpleNamespace(borrower_id=uuid4())]
    with pytest.raises(HTTPException) as ambiguous:
        module.submit_pending_cdas_consent_evidence(
            payload=request(borrower=borrower, document=document),
            context=context(company), db=db,
        )
    assert ambiguous.value.status_code == 409
    db.employees[module.BorrowerEmploymentProfile] = []
    db.document = None
    with pytest.raises(HTTPException) as missing:
        module.submit_pending_cdas_consent_evidence(
            payload=request(borrower=borrower, document=document),
            context=context(company), db=db,
        )
    assert missing.value.status_code == 404
    assert not db.added
