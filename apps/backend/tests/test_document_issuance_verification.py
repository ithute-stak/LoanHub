from types import SimpleNamespace
from unittest.mock import Mock, patch
from uuid import uuid4

from services.document_issuance_integrity import pdf_fingerprint
from services.document_issuance_verification import verify_stored_issuance


def test_missing_record_never_confirms_verification():
    db = Mock()
    db.query.return_value.filter.return_value.one_or_none.return_value = None
    assert verify_stored_issuance(
        db=db, authenticated_tenant_id=uuid4(), public_id="document-test-reference",
    ) == "not_found"


def test_only_exact_matching_pdf_is_verified():
    tenant = uuid4()
    file_id = uuid4()
    genuine = b"%PDF-1.4\ncanonical document\n"
    record = SimpleNamespace(
        artifact_key=str(file_id), status="issued",
        final_pdf_sha256=pdf_fingerprint(genuine),
    )
    stored = SimpleNamespace(
        id=file_id, company_id=tenant, visibility="private",
        is_confidential=True, is_deleted=False,
    )
    db = Mock()
    db.query.return_value.filter.return_value.one_or_none.side_effect = [record, stored]
    with patch("services.document_issuance_verification.read_file_bytes", return_value=genuine):
        assert verify_stored_issuance(
            db=db, authenticated_tenant_id=tenant,
            public_id="document-test-reference",
            submitted_pdf=genuine + b"tampered",
        ) == "altered"
    db.query.return_value.filter.return_value.one_or_none.side_effect = [record, stored]
    with patch("services.document_issuance_verification.read_file_bytes", return_value=genuine):
        assert verify_stored_issuance(
            db=db, authenticated_tenant_id=tenant,
            public_id="document-test-reference",
            submitted_pdf=genuine,
        ) == "verified"


def test_qr_lookup_without_pdf_never_claims_file_match():
    tenant = uuid4()
    stored = b"%PDF-1.4\ncanonical document\n"
    record = SimpleNamespace(
        artifact_key=str(uuid4()), status="issued",
        final_pdf_sha256=pdf_fingerprint(stored),
    )
    db = Mock()
    db.query.return_value.filter.return_value.one_or_none.side_effect = [
        record, SimpleNamespace(id=uuid4()),
    ]
    with patch("services.document_issuance_verification.read_file_bytes", return_value=stored):
        assert verify_stored_issuance(
            db=db, authenticated_tenant_id=tenant,
            public_id="document-test-reference",
        ) == "issued_file_available_not_compared"


def test_revoked_document_is_not_verified():
    db = Mock()
    db.query.return_value.filter.return_value.one_or_none.return_value = (
        SimpleNamespace(status="revoked")
    )
    assert verify_stored_issuance(
        db=db, authenticated_tenant_id=uuid4(), public_id="document-test-reference",
    ) == "revoked"
