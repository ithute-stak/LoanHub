"""Actual managed-file CDAS consent content integrity and scope checks."""
from hashlib import sha256
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from services import cdas_affordability_managed_consent_integrity as integrity


def evidence(data=b"%PDF-1.7\nexample consent\n"):
    company, borrower = uuid4(), uuid4()
    digest = sha256(data).hexdigest()
    row = SimpleNamespace(
        company_id=company, linked_entity_type="borrower_evaluation",
        linked_entity_id=str(borrower), is_deleted=False,
        quarantined_reason=None, scan_status="clean",
        mime_type="application/pdf", size_bytes=len(data),
        checksum_sha256=digest,
    )
    return row, data, company, borrower, digest


def test_real_managed_bytes_certified_against_metadata_and_approval(monkeypatch):
    file, data, company, borrower, digest = evidence()
    monkeypatch.setattr(integrity, "read_file_bytes", lambda row: data)
    assert integrity.verify_managed_cdas_consent_bytes(
        file=file, company_id=company, borrower_id=borrower,
        expected_digest=digest,
    ) == digest


@pytest.mark.parametrize("field,value", [
    ("is_deleted", True),
    ("scan_status", "validated"),
    ("quarantined_reason", "suspected malware"),
    ("linked_entity_type", "other"),
    ("mime_type", "text/plain"),
    ("size_bytes", 20 * 1024 * 1024 + 1),
])
def test_invalid_file_cannot_be_certified(monkeypatch, field, value):
    file, data, company, borrower, digest = evidence()
    setattr(file, field, value)
    monkeypatch.setattr(integrity, "read_file_bytes", lambda row: data)
    with pytest.raises(HTTPException) as denied:
        integrity.verify_managed_cdas_consent_bytes(
            file=file, company_id=company, borrower_id=borrower,
        )
    assert denied.value.status_code == 409


def test_cross_company_and_cross_borrower_rejected_before_read(monkeypatch):
    file, data, company, borrower, digest = evidence()
    monkeypatch.setattr(integrity, "read_file_bytes",
                        lambda row: (_ for _ in ()).throw(AssertionError("No I/O on scope failure")))
    for identity in (dict(company_id=uuid4(), borrower_id=borrower),
                     dict(company_id=company, borrower_id=uuid4())):
        with pytest.raises(HTTPException) as denied:
            integrity.verify_managed_cdas_consent_bytes(file=file, **identity)
        assert denied.value.status_code == 409


def test_replaced_bytes_and_wrong_reviewer_digest_fail_closed(monkeypatch):
    file, data, company, borrower, digest = evidence()
    monkeypatch.setattr(integrity, "read_file_bytes", lambda row: b"%PDF-1.7\nchanged bytes")
    with pytest.raises(HTTPException):
        integrity.verify_managed_cdas_consent_bytes(
            file=file, company_id=company, borrower_id=borrower,
        )
    monkeypatch.setattr(integrity, "read_file_bytes", lambda row: data)
    with pytest.raises(HTTPException):
        integrity.verify_managed_cdas_consent_bytes(
            file=file, company_id=company, borrower_id=borrower,
            expected_digest="b" * 64,
        )


def test_file_type_magic_mismatch_rejected_even_if_checksum_matches(monkeypatch):
    data = b"not actually a PDF"
    file, data, company, borrower, digest = evidence(data)
    monkeypatch.setattr(integrity, "read_file_bytes", lambda row: data)
    with pytest.raises(HTTPException):
        integrity.verify_managed_cdas_consent_bytes(
            file=file, company_id=company, borrower_id=borrower,
        )
