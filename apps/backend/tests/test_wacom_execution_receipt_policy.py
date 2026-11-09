"""No execution can be reserved for an altered, signed or duplicated contract."""
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from types import SimpleNamespace as R
from uuid import uuid4

import pytest
from services.wacom_execution_receipt_policy import reserve_execution_blockers


def sample():
    now = datetime(2026, 11, 9, 7, tzinfo=timezone.utc)
    company, intent_id, contract_id, approval_id, packet_id = [uuid4() for _ in range(5)]
    users = [uuid4() for _ in range(7)]
    source_pdf = b"%PDF-SYNTHETIC-CONTRACT"
    handwriting_png = b"\x89PNG\r\n\x1a\nSYNTHETIC"
    doc = sha256(source_pdf).hexdigest()
    ink = sha256(handwriting_png).hexdigest()
    common = dict(document_sha256=doc, evidence_sha256=ink, binding_sha256="a"*64)
    borrower_id, source_file_id, evidence_file_id = uuid4(), uuid4(), uuid4()
    intent = R(
        id=intent_id, company_id=company, contract_id=contract_id,
        borrower_id=borrower_id, source_file_id=source_file_id,
        evidence_file_id=evidence_file_id, document_version="1",
        operator_user_id=users[0], review_by=users[1], review_at=now,
        consent_at=now, consent_reference="consent", consent_commitment_sha256="b"*64,
        status="verified", expires_at=now+timedelta(minutes=5), **common)
    approval = R(
        id=approval_id, company_id=company, intent_id=intent_id,
        contract_id=contract_id, status="consumed", consumed_at=now,
        decided_by=users[3], requested_by=users[2],
        decided_at=now, expires_at=now+timedelta(minutes=2),
        decision_reference="approval", **common)
    packet = R(
        id=packet_id, company_id=company, intent_id=intent_id,
        contract_id=contract_id, approval_id=approval_id,
        archived_at=now, packet_file_id=uuid4(), created_by_user_id=users[4],
        source_sha256=doc, handwriting_sha256=ink)
    permit = R(
        company_id=company, intent_id=intent_id, contract_id=contract_id,
        packet_id=packet_id, status="approved", consumed_at=None,
        authorized_by=users[5], authorized_at=now, expires_at=now+timedelta(minutes=1),
        **common)
    contract = R(
        company_id=company, id=contract_id, borrower_id=borrower_id,
        pdf_file_id=source_file_id, version=1, status="draft",
        borrower_signed_at=None, locked_at=None)
    source = R(
        id=source_file_id, company_id=company, checksum_sha256=doc,
        mime_type="application/pdf", is_encrypted=True, is_deleted=False,
        scan_status="clean")
    evidence = R(
        id=evidence_file_id, company_id=company, checksum_sha256=ink,
        category="wacom_client_capture_verified", linked_entity_id=str(borrower_id),
        linked_entity_type="wacom_client", is_encrypted=True,
        is_confidential=True, is_deleted=False, scan_status="clean")
    return dict(intent=intent, approval=approval, packet=packet,
                execution_authorization=permit, contract=contract,
                source=source, evidence=evidence, executing_user_id=users[6],
                source_pdf=source_pdf, handwriting_png=handwriting_png,
                existing_receipt=None, now=now)


def reasons(v):
    return reserve_execution_blockers(**v)


def test_clean_synthetic_reservation_eligible_without_executing():
    assert reasons(sample()) == []


@pytest.mark.parametrize("target,attribute,value,reason", [
    ("contract", "status", "signed", "contract_already_signed"),
    ("contract", "borrower_signed_at", datetime(2026,11,9,tzinfo=timezone.utc), "contract_already_signed"),
    ("contract", "version", 2, "contract_identity_changed"),
    ("contract", "company_id", uuid4(), "contract_identity_changed"),
    ("source", "is_encrypted", False, "source_unavailable"),
    ("source", "scan_status", "pending", "source_unavailable"),
    ("evidence", "is_confidential", False, "evidence_unavailable"),
    ("evidence", "linked_entity_id", "other", "evidence_unavailable"),
    ("execution_authorization", "packet_id", uuid4(), "execution_packet_mismatch"),
    ("execution_authorization", "authorized_at", None, "execution_decision_missing"),
])
def test_rejects_invalid_reservation(target, attribute, value, reason):
    v = sample()
    setattr(v[target], attribute, value)
    assert reason in reasons(v)


def test_rejects_duplicate_receipt():
    v = sample()
    v["existing_receipt"] = R(id=uuid4(), status="reserved")
    assert "contract_already_reserved" in reasons(v)


def test_rejects_changed_source_and_evidence_bytes():
    v = sample()
    v["source_pdf"] += b"tampered"
    v["handwriting_png"] += b"tampered"
    failures = reasons(v)
    assert "source_bytes_mismatch" in failures
    assert "handwriting_bytes_mismatch" in failures
    assert "source_file_bytes_changed" in failures
    assert "evidence_file_bytes_changed" in failures


def test_receipt_schema_has_uniqueness_guards():
    from database.models.wacom_execution_receipt import WacomExecutionReceipt
    constraints = WacomExecutionReceipt.__table__.constraints
    unique = {tuple(sorted(c.columns.keys())) for c in constraints if c.__class__.__name__ == "UniqueConstraint"}
    assert ("company_id", "contract_id") in unique
    assert ("authorization_id",) in unique
    assert ("intent_id",) in unique


def test_no_direct_execution_in_policy():
    import inspect
    from services import wacom_execution_receipt_policy as policy
    source = inspect.getsource(policy)
    for forbidden in ("db.commit(", "PdfWriter(", "store_bytes(", "borrower_signed_at ="):
        assert forbidden not in source
