"""Independent Wacom capture review is separate from document signing."""
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException, Response

from routers import local_signature_review as review


class Query:
    def __init__(self, rows):
        self.rows = rows
        self.locked = False
    def filter(self, *args):
        return self
    def order_by(self, *args):
        return self
    def limit(self, value):
        assert 1 <= value <= 100
        return self
    def all(self):
        return self.rows
    def one_or_none(self):
        return self.rows[0] if self.rows else None
    def with_for_update(self):
        self.locked = True
        return self


class DB:
    def __init__(self, rows):
        self.q = Query(rows)
        self.writes = []
        self.commits = 0
    def query(self, model):
        assert model is review.ManagedFile
        return self.q
    def add(self, row):
        self.writes.append(row)
    def commit(self):
        self.commits += 1


def reviewer_context(owner_id=None):
    reviewer_id = uuid4()
    return SimpleNamespace(
        company_id=uuid4(),
        branch_id=uuid4(),
        staff=SimpleNamespace(role=next(iter(review.COMPANY_MANAGEMENT_ROLES))),
        user=SimpleNamespace(id=owner_id or reviewer_id),
        role=next(iter(review.COMPANY_MANAGEMENT_ROLES)),
    )


def sample_record(company_id, owner_id=None):
    return SimpleNamespace(
        id=uuid4(), company_id=company_id, branch_id=uuid4(),
        owner_user_id=owner_id or uuid4(), category="wacom_client_signature_pending",
        linked_entity_type="wacom_client", linked_entity_id=str(uuid4()),
        is_deleted=False, is_encrypted=True, is_confidential=True,
        scan_status="clean", visibility="private", mime_type="image/png",
        size_bytes=44, checksum_sha256="1"*64, created_at=None,
    )


def test_review_routes_registered():
    from api.v1.router import api_router
    paths={route.path for route in api_router.routes}
    assert "/local-signatures/review" in paths
    assert "/local-signatures/review/{file_id}/preview" in paths
    assert "/local-signatures/review/{file_id}/decision" in paths


def test_review_queue_is_metadata_only(monkeypatch):
    ctx=reviewer_context()
    db=DB([sample_record(ctx.company_id)])
    monkeypatch.setattr(review,"require_tenant_roles",lambda *_: None)
    result=review.pending_evidence(Response(),50,db,ctx)
    assert result["captures"][0]["evidence_status"]=="pending_review"
    assert result["captures"][0]["usable_for_signing"] is False
    assert result["captures"][0]["automatic_reuse_allowed"] is False
    assert "checksum_sha256" not in result["captures"][0]
    assert db.commits==0


def test_reviewer_cannot_verify_own_capture(monkeypatch):
    ctx=reviewer_context()
    record=sample_record(ctx.company_id,owner_id=ctx.user.id)
    db=DB([record])
    monkeypatch.setattr(review,"require_tenant_roles",lambda *_: None)
    body=review.EvidenceDecision(
        decision="verify",identity_checked=True,consent_checked=True,
        evidence_reference="ID-CHECK-123",reason="Verified identity and consent evidence",
    )
    with pytest.raises(HTTPException) as err:
        review.review_capture(record.id,body,Response(),db,ctx)
    assert err.value.status_code==403
    assert record.category=="wacom_client_signature_pending"
    assert db.commits==0
    assert db.q.locked


def test_review_requires_clean_scan_encryption_and_consent(monkeypatch):
    ctx=reviewer_context()
    monkeypatch.setattr(review,"require_tenant_roles",lambda *_: None)
    for field,value in [
        ("is_encrypted",False),("scan_status","scanner_unavailable"),
        ("linked_entity_id",None),
    ]:
        record=sample_record(ctx.company_id)
        setattr(record,field,value)
        db=DB([record])
        payload=review.EvidenceDecision(
            decision="verify",identity_checked=True,consent_checked=True,
            evidence_reference="IDENTITY-OK",reason="Independent checks completed",
        )
        with pytest.raises(HTTPException) as err:
            review.review_capture(record.id,payload,Response(),db,ctx)
        assert err.value.status_code==409
        assert db.commits==0
    record=sample_record(ctx.company_id)
    db=DB([record])
    body=review.EvidenceDecision(
        decision="verify",identity_checked=False,consent_checked=True,
        evidence_reference="IDENTITY-OK",reason="Independent checks completed",
    )
    with pytest.raises(HTTPException) as err:
        review.review_capture(record.id,body,Response(),db,ctx)
    assert err.value.status_code==422
    assert db.commits==0


def test_review_verifies_only_evidence_not_a_contract(monkeypatch):
    ctx=reviewer_context()
    record=sample_record(ctx.company_id)
    db=DB([record])
    monkeypatch.setattr(review,"require_tenant_roles",lambda *_: None)
    payload=review.EvidenceDecision(
        decision="verify",identity_checked=True,consent_checked=True,
        evidence_reference="MANUAL-KYC-001",
        reason="Consent and identity were independently checked",
    )
    result=review.review_capture(record.id,payload,Response(),db,ctx)
    assert db.commits==1
    assert record.category=="wacom_client_capture_verified"
    assert result["evidence_status"]=="verified"
    assert result["usable_for_signing"] is False
    assert result["automatic_reuse_allowed"] is False
    assert len(db.writes)==1
    audit=db.writes[0]
    assert audit.action=="local_signatures.capture_reviewed"
    assert audit.event_data["authorizes_signing"] is False
    assert audit.event_data["submitted_by_user_id"]==str(record.owner_user_id)


def test_review_rejection_never_promotes_signature(monkeypatch):
    ctx=reviewer_context()
    record=sample_record(ctx.company_id)
    db=DB([record])
    monkeypatch.setattr(review,"require_tenant_roles",lambda *_: None)
    payload=review.EvidenceDecision(
        decision="reject",identity_checked=False,consent_checked=False,
        evidence_reference="REJECTION-001",
        reason="Signer identity could not be established",
    )
    response=review.review_capture(record.id,payload,Response(),db,ctx)
    assert response["evidence_status"]=="rejected"
    assert response["usable_for_signing"] is False
    assert record.category=="wacom_client_capture_rejected"


def test_review_requires_management_role(monkeypatch):
    ctx=reviewer_context()
    ctx.staff=None
    db=DB([])
    with pytest.raises(HTTPException) as err:
        review.pending_evidence(Response(),50,db,ctx)
    assert err.value.status_code==403


def test_missing_pending_record_never_updates(monkeypatch):
    ctx=reviewer_context()
    db=DB([])
    monkeypatch.setattr(review,"require_tenant_roles",lambda *_: None)
    body=review.EvidenceDecision(
        decision="reject",evidence_reference="REJECTION-001",
        reason="Signer unavailable for inspection",
    )
    with pytest.raises(HTTPException) as err:
        review.review_capture(uuid4(),body,Response(),db,ctx)
    assert err.value.status_code==404
    assert db.commits==0
