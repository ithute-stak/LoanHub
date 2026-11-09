"""Wacom recovery certifies archived file bytes without modifying evidence."""
from hashlib import sha256
from types import SimpleNamespace as R
from uuid import uuid4

import pytest

from services.wacom_storage_content_audit import verify_candidate_contents


def snapshot():
    company, file_id, receipt_id = uuid4(), uuid4(), uuid4()
    pdf = b"%PDF-1.4\nsynthetic candidate\n%%EOF"
    digest = sha256(pdf).hexdigest()
    file = R(
        id=file_id, company_id=company, category="wacom_execution_candidate",
        is_deleted=False, is_encrypted=True, is_confidential=True,
        scan_status="clean", mime_type="application/pdf", checksum_sha256=digest,
    )
    receipt = R(
        id=receipt_id, company_id=company,
        executed_file_id=file_id, executed_pdf_sha256=digest,
    )
    return dict(company_id=company, managed_files=[file], receipts=[receipt]), pdf


def check(rows, reader):
    return verify_candidate_contents(**rows, read_bytes=reader)


def codes(findings):
    return [f.code for f in findings]


def test_verified_candidate_bytes():
    rows, pdf = snapshot()
    assert check(rows, lambda f: pdf) == []


def test_storage_failure_is_reported_without_retry_or_cleanup():
    rows, _ = snapshot()
    calls = []
    def broken(f):
        calls.append(f.id)
        raise IOError("synthetic storage loss")
    assert codes(check(rows, broken)) == ["candidate_contents_unavailable"]
    assert calls == [rows["managed_files"][0].id]


def test_payload_tampering_rejected():
    rows, pdf = snapshot()
    assert "candidate_contents_hash_mismatch" in codes(
        check(rows, lambda f: pdf + b"tampered")
    )


def test_opaque_or_non_pdf_payload_rejected():
    rows, _ = snapshot()
    assert "candidate_contents_not_pdf" in codes(
        check(rows, lambda f: b"not a pdf")
    )


@pytest.mark.parametrize("attribute,value", [
    ("scan_status", "pending"),
    ("is_encrypted", False),
    ("is_confidential", False),
    ("is_deleted", True),
    ("mime_type", "application/octet-stream"),
])
def test_untrusted_metadata_never_reads_contents(attribute, value):
    rows, pdf = snapshot()
    setattr(rows["managed_files"][0], attribute, value)
    def must_not_read(f):
        raise AssertionError("Untrusted file was read")
    assert codes(check(rows, must_not_read)) == [
        "candidate_file_security_metadata_invalid"
    ]


def test_receipt_hash_mismatch_detected():
    rows, pdf = snapshot()
    rows["receipts"][0].executed_pdf_sha256 = "f" * 64
    assert "candidate_contents_hash_mismatch" in codes(
        check(rows, lambda f: pdf)
    )


def test_missing_candidate_metadata_not_a_valid_result():
    rows, pdf = snapshot()
    rows["managed_files"] = []
    assert "candidate_metadata_not_available_for_byte_verification" in codes(
        check(rows, lambda f: pdf)
    )


def test_cross_tenant_input_rejected_before_read():
    rows, pdf = snapshot()
    rows["managed_files"][0].company_id = uuid4()
    with pytest.raises(ValueError, match="Cross-company"):
        check(rows, lambda f: pdf)


def test_receipt_replay_does_not_re_read_same_candidate():
    rows, pdf = snapshot()
    rows["receipts"].append(R(
        id=uuid4(), company_id=rows["company_id"],
        executed_file_id=rows["managed_files"][0].id,
        executed_pdf_sha256=sha256(pdf).hexdigest(),
    ))
    reads = []
    assert "candidate_referenced_by_multiple_receipts" in codes(
        check(rows, lambda f: reads.append(f.id) or pdf)
    )
    assert len(reads) == 1


def test_no_storage_or_database_mutations():
    import inspect
    from services import wacom_storage_content_audit as svc
    from scripts import wacom_reconcile_storage as cli
    code = inspect.getsource(svc) + inspect.getsource(cli)
    assert "db.commit(" not in code
    assert ".delete(" not in code
    assert "borrower_signed_at =" not in code
