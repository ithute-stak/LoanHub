"""Verify CDAS reviewer document downloads are scoped, private and fail closed."""
from hashlib import sha256
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from routers import cdas_government_employees as module


class Query:
    def __init__(self, value):
        self.value = value
    def filter(self, *clauses):
        assert clauses
        return self
    def first(self):
        return self.value


class DB:
    def __init__(self, record=None, file=None):
        self.record, self.file = record, file
    def query(self, model):
        if model is module.CdasAffordabilityConsentEvidence:
            return Query(self.record)
        if model is module.ManagedFile:
            return Query(self.file)
        raise AssertionError("Unexpected query")


def fixture():
    company, borrower, submitter, reviewer = (uuid4() for _ in range(4))
    record = SimpleNamespace(
        id=uuid4(), company_id=company, borrower_id=borrower,
        managed_file_id=uuid4(), submitted_by_user_id=submitter,
        status="pending",
    )
    file = SimpleNamespace(
        id=record.managed_file_id, company_id=company,
        mime_type="application/pdf",
    )
    context = SimpleNamespace(company_id=company, user=SimpleNamespace(id=reviewer))
    return record, DB(record, file), context


def test_authorized_independent_review_has_no_store_headers_and_digest(monkeypatch):
    record, db, context = fixture()
    body = b"%PDF-1.7\nverified reviewer evidence"
    calls = []
    monkeypatch.setattr(module, "_require_company_manager", lambda ctx: None)
    def verify(**kwargs):
        calls.append(kwargs)
        return sha256(body).hexdigest()
    monkeypatch.setattr(module, "verify_managed_cdas_consent_bytes", verify)
    from services import file_service
    monkeypatch.setattr(file_service, "read_file_bytes", lambda file: body)
    response = module.download_cdas_consent_review_document(
        evidence_id=record.id, context=context, db=db,
    )
    assert response.headers["cache-control"] == "private, no-store, max-age=0"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["content-length"] == str(len(body))
    assert calls[0]["borrower_id"] == record.borrower_id
    assert calls[0]["company_id"] == context.company_id


@pytest.mark.parametrize("status", ["approved", "rejected", "revoked"])
def test_only_pending_document_is_downloadable(monkeypatch, status):
    record, db, context = fixture()
    record.status = status
    monkeypatch.setattr(module, "_require_company_manager", lambda ctx: None)
    with pytest.raises(HTTPException) as blocked:
        module.download_cdas_consent_review_document(record.id, context, db)
    assert blocked.value.status_code == 409


def test_submitter_cannot_use_reviewer_document_download(monkeypatch):
    record, db, context = fixture()
    context.user.id = record.submitted_by_user_id
    monkeypatch.setattr(module, "_require_company_manager", lambda ctx: None)
    with pytest.raises(HTTPException) as blocked:
        module.download_cdas_consent_review_document(record.id, context, db)
    assert blocked.value.status_code == 403


def test_non_manager_blocked_before_document_query(monkeypatch):
    record, db, context = fixture()
    def denied(_context):
        raise HTTPException(403, "Management required")
    monkeypatch.setattr(module, "_require_company_manager", denied)
    with pytest.raises(HTTPException) as blocked:
        module.download_cdas_consent_review_document(record.id, context, db)
    assert blocked.value.status_code == 403


def test_changed_bytes_cannot_be_downloaded(monkeypatch):
    record, db, context = fixture()
    monkeypatch.setattr(module, "_require_company_manager", lambda ctx: None)
    monkeypatch.setattr(module, "verify_managed_cdas_consent_bytes",
                        lambda **kwargs: sha256(b"old").hexdigest())
    from services import file_service
    monkeypatch.setattr(file_service, "read_file_bytes", lambda file: b"new")
    with pytest.raises(HTTPException) as blocked:
        module.download_cdas_consent_review_document(record.id, context, db)
    assert blocked.value.status_code == 409


def test_missing_binding_cannot_be_downloaded(monkeypatch):
    record, db, context = fixture()
    record.managed_file_id = None
    monkeypatch.setattr(module, "_require_company_manager", lambda ctx: None)
    with pytest.raises(HTTPException) as blocked:
        module.download_cdas_consent_review_document(record.id, context, db)
    assert blocked.value.status_code == 409
