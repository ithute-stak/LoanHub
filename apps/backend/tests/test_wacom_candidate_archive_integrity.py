"""Independent archived Wacom PDF verification and fail-closed tests."""
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from io import BytesIO
from types import SimpleNamespace as R
from uuid import uuid4

import pytest
from reportlab.pdfgen import canvas
from services import wacom_candidate_archive_integrity as checker
from routers import wacom_candidate_verification as routes
from fastapi import HTTPException


def test_route_disabled_by_default(monkeypatch):
    monkeypatch.delenv(routes.FLAG, raising=False)
    with pytest.raises(HTTPException) as exc:
        routes._gate()
    assert exc.value.status_code == 503


def make_data():
    now = datetime.now(timezone.utc)
    ids = [uuid4() for _ in range(12)]
    (company, contract_id, intent_id, approval_id, packet_id, authorization_id,
     receipt_id, source_id, evidence_id, packet_file_id, candidate_id, borrower_id) = ids
    buf = BytesIO()
    pdf = canvas.Canvas(buf, pagesize=(612, 792))
    pdf.drawString(90, 700, "synthetic source contract")
    pdf.save()
    source_bytes = buf.getvalue()
    buf = BytesIO()
    pdf = canvas.Canvas(buf, pagesize=(612, 792))
    pdf.drawString(90, 700, "synthetic contract with sample handwriting")
    pdf.save()
    candidate_bytes = buf.getvalue()
    ink_bytes = b"synthetic handwriting"
    packet_bytes = b"synthetic evidence packet"
    ds = sha256(source_bytes).hexdigest()
    es = sha256(ink_bytes).hexdigest()
    ps = sha256(packet_bytes).hexdigest()
    cs = sha256(candidate_bytes).hexdigest()
    binding = "c" * 64
    field_hash = "f" * 64
    intent = R(
        id=intent_id, company_id=company, contract_id=contract_id,
        borrower_id=borrower_id, source_file_id=source_id, evidence_file_id=evidence_id,
        document_sha256=ds, evidence_sha256=es, binding_sha256=binding,
        status="verified", consent_reference="test-consent",
        consent_commitment_sha256="a"*64, review_reference="test-review",
        review_by=uuid4(),
    )
    approval = R(
        id=approval_id, intent_id=intent_id, company_id=company,
        status="consumed", consumed_at=now, decided_by=uuid4(),
        decision_reference="test-approval",
        document_sha256=ds, evidence_sha256=es, binding_sha256=binding,
    )
    packet = R(
        id=packet_id, company_id=company, intent_id=intent_id,
        approval_id=approval_id, packet_file_id=packet_file_id,
        archived_at=now, source_sha256=ds, handwriting_sha256=es,
        packet_sha256=ps,
    )
    permit = R(
        id=authorization_id, company_id=company, intent_id=intent_id,
        status="approved", consumed_at=None, authorized_by=uuid4(),
        authorized_at=now-timedelta(minutes=1),
        expires_at=now+timedelta(minutes=1),
        field_binding_sha256=field_hash, field_page_count=1,
        document_sha256=ds, evidence_sha256=es, binding_sha256=binding,
    )
    receipt = R(
        id=receipt_id, company_id=company, contract_id=contract_id,
        intent_id=intent_id, authorization_id=authorization_id,
        packet_id=packet_id, executed_file_id=candidate_id,
        executed_pdf_sha256=cs, status="reserved", executed_at=None,
        reserved_at=now, field_binding_sha256=field_hash,
        document_sha256=ds, evidence_sha256=es, binding_sha256=binding,
    )
    contract = R(id=contract_id, company_id=company, borrower_id=borrower_id)
    def file(id, digest, **extra):
        return R(
            id=id, company_id=company, is_deleted=False, is_encrypted=True,
            scan_status="clean", checksum_sha256=digest,
            **extra,
        )
    return dict(
        receipt=receipt, intent=intent, approval=approval, packet=packet,
        authorization=permit, contract=contract,
        source_file=file(source_id, ds),
        evidence_file=file(evidence_id, es),
        packet_file=file(packet_file_id, ps),
        candidate_file=file(candidate_id, cs, is_confidential=True,
                            category="wacom_execution_candidate",
                            mime_type="application/pdf"),
        source_pdf=source_bytes, handwriting_png=ink_bytes,
        packet_pdf=packet_bytes, candidate_pdf=candidate_bytes,
    )


@pytest.fixture(autouse=True)
def stub_field_binding(monkeypatch):
    monkeypatch.setattr(checker, "stored_field_matches", lambda **kwargs: True)


def blockers(v):
    return checker.candidate_archive_blockers(**v)


def test_valid_synthetic_chain_is_integrity_verified_not_signed():
    assert blockers(make_data()) == []


@pytest.mark.parametrize("record,attr,value,expected", [
    ("receipt", "status", "executed", "candidate_receipt_state_changed"),
    ("receipt", "field_binding_sha256", "0"*64, "candidate_receipt_state_changed"),
    ("receipt", "company_id", uuid4(), "cross_tenant_archive"),
    ("authorization", "status", "consumed", "execution_permit_state_changed"),
    ("approval", "status", "pending", "evidence_archive_not_approved"),
    ("candidate_file", "is_encrypted", False, "archived_file_integrity_failure"),
    ("candidate_file", "scan_status", "pending", "archived_file_integrity_failure"),
    ("candidate_file", "category", "general", "candidate_storage_classification_changed"),
    ("packet", "approval_id", uuid4(), "archive_reference_chain_changed"),
    ("receipt", "authorization_id", uuid4(), "archive_reference_chain_changed"),
])
def test_rejects_changed_chain(record, attr, value, expected):
    v = make_data()
    setattr(v[record], attr, value)
    assert expected in blockers(v)


def test_changed_pdf_bytes_fail():
    v = make_data()
    v["candidate_pdf"] += b"altered"
    assert "archived_file_integrity_failure" in blockers(v)


def test_rejects_same_pdf_as_source():
    v = make_data()
    v["candidate_pdf"] = v["source_pdf"]
    v["receipt"].executed_pdf_sha256 = sha256(v["source_pdf"]).hexdigest()
    v["candidate_file"].checksum_sha256 = v["receipt"].executed_pdf_sha256
    assert "candidate_does_not_change_original" in blockers(v)


def test_archives_remain_verifiable_after_permit_expires():
    v = make_data()
    v["authorization"].expires_at = v["receipt"].reserved_at + timedelta(seconds=1)
    assert blockers(v) == []


def test_rejects_archive_outside_original_authorized_window():
    v = make_data()
    v["receipt"].reserved_at += timedelta(minutes=10)
    assert "archive_outside_authorized_window" in blockers(v)


def test_no_mutation_or_legal_signing_claims():
    import inspect
    code = inspect.getsource(checker) + inspect.getsource(routes)
    for forbidden in ("db.commit(", "contract.status =", "borrower_signed_at =", "store_bytes("):
        assert forbidden not in code
