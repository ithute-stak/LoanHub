from types import SimpleNamespace
from unittest.mock import Mock, patch
from uuid import uuid4

import pytest

from database.models.enums import UserRole
from services.document_issuance_finalization import finalize_and_register_document


PDF = b"%PDF-1.4\noriginal and immutable final bytes\n"
DIGEST = "f" * 64
PUBLIC_ID = "example-secure-public-id-12345"


def _context():
    tenant = uuid4()
    return SimpleNamespace(
        company_id=tenant,
        company=SimpleNamespace(id=tenant),
        user=SimpleNamespace(id=uuid4()),
        branch_id=None,
        staff=SimpleNamespace(role=UserRole.COMPANY_ADMIN),
        is_platform_admin=False,
    )


def _run(db, context):
    return finalize_and_register_document(
        db=db, context=context, source_pdf=PDF,
        trusted_verification_origin="https://verify.example.test",
        source_type="workspace", source_id="doc123",
        document_type="agreement", idempotency_key="one-request",
        version=1, stamp_configuration_version=1,
    )


def test_finalization_only_returns_after_commit():
    db = Mock()
    db.query.return_value.filter.return_value.one_or_none.return_value = None
    context = _context()
    file = SimpleNamespace(id=uuid4(), scan_status="clean")
    entry = SimpleNamespace(
        id=uuid4(), public_id=PUBLIC_ID,
        final_pdf_sha256=DIGEST, artifact_key=str(file.id),
    )
    candidate = SimpleNamespace(pdf_bytes=PDF, public_id=PUBLIC_ID, sha256_hex=DIGEST)
    event_order = []
    db.commit.side_effect = lambda: event_order.append("commit")
    def checked_read(_):
        event_order.append("read-back")
        return PDF
    with patch("services.document_issuance_finalization.prepare_stamped_document_candidate", return_value=candidate), \
         patch("services.document_issuance_finalization.store_bytes", return_value=file), \
         patch("services.document_issuance_finalization.read_file_bytes", side_effect=checked_read), \
         patch("services.document_issuance_finalization.pdf_fingerprint", return_value=DIGEST), \
         patch("services.document_issuance_finalization.register_stored_pdf_issuance", return_value=entry):
        result = _run(db, context)
    assert result.document_bytes == PDF
    assert result.public_id == PUBLIC_ID
    assert event_order == ["read-back", "commit"]
    db.rollback.assert_not_called()


def test_commit_failure_does_not_release_final_pdf():
    db = Mock()
    db.commit.side_effect = RuntimeError("database commit failed")
    context = _context()
    file = SimpleNamespace(id=uuid4(), scan_status="clean")
    entry = SimpleNamespace(
        id=uuid4(), public_id=PUBLIC_ID,
        final_pdf_sha256=DIGEST, artifact_key=str(file.id),
    )
    candidate = SimpleNamespace(pdf_bytes=PDF, public_id=PUBLIC_ID, sha256_hex=DIGEST)
    with patch("services.document_issuance_finalization.prepare_stamped_document_candidate", return_value=candidate), \
         patch("services.document_issuance_finalization.store_bytes", return_value=file), \
         patch("services.document_issuance_finalization.read_file_bytes", return_value=PDF), \
         patch("services.document_issuance_finalization.pdf_fingerprint", return_value=DIGEST), \
         patch("services.document_issuance_finalization.register_stored_pdf_issuance", return_value=entry):
        with pytest.raises(RuntimeError, match="commit failed"):
            _run(db, context)
    db.rollback.assert_called_once()


def test_failed_malware_check_blocks_registration_and_commit():
    db = Mock()
    context = _context()
    file = SimpleNamespace(id=uuid4(), scan_status="validated")
    candidate = SimpleNamespace(pdf_bytes=PDF, public_id=PUBLIC_ID, sha256_hex=DIGEST)
    with patch("services.document_issuance_finalization.prepare_stamped_document_candidate", return_value=candidate), \
         patch("services.document_issuance_finalization.store_bytes", return_value=file), \
         patch("services.document_issuance_finalization.register_stored_pdf_issuance") as register:
        with pytest.raises(ValueError, match="clean malware scan"):
            _run(db, context)
    register.assert_not_called()
    db.commit.assert_not_called()
    db.rollback.assert_called_once()


def test_wrong_tenant_rejected_before_render_or_write():
    db = Mock()
    context = _context()
    context.company.id = uuid4()
    with patch("services.document_issuance_finalization.store_bytes") as store:
        with pytest.raises(PermissionError):
            _run(db, context)
    store.assert_not_called()
    db.commit.assert_not_called()


def test_previously_issued_request_never_creates_second_pdf():
    db = Mock()
    db.query.return_value.filter.return_value.one_or_none.return_value = (
        SimpleNamespace(status="issued")
    )
    with patch("services.document_issuance_finalization.prepare_stamped_document_candidate") as prepare, \
         patch("services.document_issuance_finalization.store_bytes") as store:
        with pytest.raises(ValueError, match="already registered"):
            _run(db, _context())
    prepare.assert_not_called()
    store.assert_not_called()
    db.commit.assert_not_called()


def test_revoked_request_not_resurrected_by_retry():
    db = Mock()
    db.query.return_value.filter.return_value.one_or_none.return_value = (
        SimpleNamespace(status="revoked")
    )
    with patch("services.document_issuance_finalization.store_bytes") as store:
        with pytest.raises(ValueError, match="already registered"):
            _run(db, _context())
    store.assert_not_called()
