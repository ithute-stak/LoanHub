"""Staging PDF flow must scan twice and never issue on unsafe input."""
from hashlib import sha256
from types import SimpleNamespace
from unittest.mock import Mock, patch
from uuid import uuid4

import pytest

from database.models.enums import UserRole
from services.document_issuance_immutable_s3 import S3ObjectLockPdfStore
from services.document_issuance_immutable_staging import stage_locked_document_candidate
from services.object_storage_service import StorageUnavailableError


PDF = b"%PDF-1.4\nfinal\n"


@pytest.fixture(autouse=True)
def _approved_stamp_database_gate():
    # Existing staging tests focus on rendering, malware, QR and storage.
    # Dedicated cases below exercise approval failures explicitly.
    with patch(
        "services.document_issuance_immutable_staging.lookup_approved_stamp_from_database"
    ):
        yield


def _context():
    company_id = uuid4()
    return SimpleNamespace(
        company_id=company_id,
        company=SimpleNamespace(
            id=company_id, name="Example Tenant (Pty) Ltd",
            address="Maseru", phone="+266 50000000",
            email="tenant@example.test", registration_number="REG-1",
            license_number="LIC-1",
        ),
        user=SimpleNamespace(id=uuid4()),
        staff=SimpleNamespace(role=UserRole.COMPANY_ADMIN),
        is_platform_admin=False,
    )


def _store():
    # An instance of the exact supported adapter, but no external S3 calls.
    obj = object.__new__(S3ObjectLockPdfStore)
    obj.bucket = "staging-locked"
    obj.put_locked_pdf = Mock()
    obj.read_exact_version = Mock(return_value=PDF)
    return obj


def _stage(context, store):
    return stage_locked_document_candidate(
        context=context, source_pdf=PDF,
        trusted_verification_origin="https://verify.example.test",
        store=store, db=Mock(), stamp_configuration_version=1,
    )


def test_successful_staging_scans_twice_and_reads_exact_version():
    context, store = _context(), _store()
    candidate = SimpleNamespace(
        tenant_id=context.company_id, pdf_bytes=PDF,
        public_id="valid-public-id-12345", sha256_hex=sha256(PDF).hexdigest(),
        verification_url="https://verify.example.test/verify/valid-public-id-12345",
    )
    locked = SimpleNamespace(sha256_hex=candidate.sha256_hex)
    store.put_locked_pdf.return_value = locked
    with patch("services.document_issuance_immutable_staging.settings") as settings, \
         patch("services.document_issuance_immutable_staging.scan_upload", return_value="clean") as scan, \
         patch("services.document_issuance_immutable_staging.prepare_stamped_document_candidate",
               return_value=candidate):
        settings.MALWARE_SCAN_ENABLED = True
        settings.MALWARE_SCAN_FAIL_CLOSED = True
        result = _stage(context, store)
    assert result.locked is locked
    assert result.source_sha256_hex == sha256(PDF).hexdigest()
    assert len(result.stamp_snapshot_sha256_hex) == 64
    assert scan.call_count == 2
    store.put_locked_pdf.assert_called_once()
    store.read_exact_version.assert_called_once_with(locked)


@pytest.mark.parametrize("enabled,fail_closed", [(False, True), (True, False)])
def test_scanner_must_be_enabled_and_fail_closed(enabled, fail_closed):
    context, store = _context(), _store()
    with patch("services.document_issuance_immutable_staging.settings") as settings:
        settings.MALWARE_SCAN_ENABLED = enabled
        settings.MALWARE_SCAN_FAIL_CLOSED = fail_closed
        with pytest.raises(PermissionError, match="malware scanning"):
            _stage(context, store)
    store.put_locked_pdf.assert_not_called()


@pytest.mark.parametrize("scan_results", [
    ["not_enabled"], ["clean", "indeterminate"], ["clean", "scanner_unavailable"],
])
def test_failed_source_or_final_scan_prevents_storage(scan_results):
    context, store = _context(), _store()
    candidate = SimpleNamespace(
        tenant_id=context.company_id, pdf_bytes=PDF,
        public_id="valid-public-id-12345", sha256_hex=sha256(PDF).hexdigest(),
        verification_url="https://verify.example.test/verify/valid-public-id-12345",
    )
    with patch("services.document_issuance_immutable_staging.settings") as settings, \
         patch("services.document_issuance_immutable_staging.scan_upload", side_effect=scan_results), \
         patch("services.document_issuance_immutable_staging.prepare_stamped_document_candidate",
               return_value=candidate):
        settings.MALWARE_SCAN_ENABLED = True
        settings.MALWARE_SCAN_FAIL_CLOSED = True
        with pytest.raises(PermissionError):
            _stage(context, store)
    store.put_locked_pdf.assert_not_called()


def test_wrong_company_rejected_before_upload():
    context, store = _context(), _store()
    context.company.id = uuid4()
    with pytest.raises(PermissionError):
        _stage(context, store)
    store.put_locked_pdf.assert_not_called()


def test_wrong_version_bytes_never_count_as_staged():
    context, store = _context(), _store()
    candidate = SimpleNamespace(
        tenant_id=context.company_id, pdf_bytes=PDF,
        public_id="valid-public-id-12345", sha256_hex=sha256(PDF).hexdigest(),
        verification_url="https://verify.example.test/verify/valid-public-id-12345",
    )
    store.put_locked_pdf.return_value = SimpleNamespace(sha256_hex=candidate.sha256_hex)
    store.read_exact_version.return_value = PDF + b"altered"
    with patch("services.document_issuance_immutable_staging.settings") as settings, \
         patch("services.document_issuance_immutable_staging.scan_upload", return_value="clean"), \
         patch("services.document_issuance_immutable_staging.prepare_stamped_document_candidate",
               return_value=candidate):
        settings.MALWARE_SCAN_ENABLED = True
        settings.MALWARE_SCAN_FAIL_CLOSED = True
        with pytest.raises(StorageUnavailableError, match="Exact locked"):
            _stage(context, store)


def test_mutable_storage_adapter_is_rejected():
    context = _context()
    store = SimpleNamespace(provider="s3")
    # Satisfy the independent scanning preflight, so this test specifically
    # verifies the immutable-adapter boundary instead of the scanner guard.
    with patch("services.document_issuance_immutable_staging.settings") as settings:
        settings.MALWARE_SCAN_ENABLED = True
        settings.MALWARE_SCAN_FAIL_CLOSED = True
        with pytest.raises(PermissionError, match="S3 Object Lock"):
            _stage(context, store)


@pytest.mark.parametrize("overrides,expected", [
    ({"public_id": "bad/slash/path"}, "public identity"),
    ({"public_id": "too-short"}, "public identity"),
    ({"sha256_hex": "0" * 64}, "fingerprint"),
    ({"pdf_bytes": b"not-a-pdf"}, "not a PDF"),
])
def test_malformed_rendered_candidates_never_reach_immutable_storage(overrides, expected):
    context, store = _context(), _store()
    candidate = SimpleNamespace(
        tenant_id=context.company_id, pdf_bytes=PDF,
        public_id="valid-public-id-12345",
        sha256_hex=sha256(PDF).hexdigest(),
        verification_url="https://verify.example.test/verify/valid-public-id-12345",
    )
    for field, value in overrides.items():
        setattr(candidate, field, value)
    with patch("services.document_issuance_immutable_staging.settings") as settings, \
         patch("services.document_issuance_immutable_staging.scan_upload", return_value="clean"), \
         patch("services.document_issuance_immutable_staging.prepare_stamped_document_candidate",
               return_value=candidate):
        settings.MALWARE_SCAN_ENABLED = True
        settings.MALWARE_SCAN_FAIL_CLOSED = True
        with pytest.raises(ValueError, match=expected):
            _stage(context, store)
    store.put_locked_pdf.assert_not_called()


@pytest.mark.parametrize("locator", [
    "https://malicious.example.test/verify/valid-public-id-12345",
    "http://verify.example.test/verify/valid-public-id-12345",
    "https://verify.example.test/verify/another-public-id",
    "https://verify.example.test/verify/valid-public-id-12345?redirect=1",
])
def test_untrusted_qr_locator_rejected_before_any_immutable_upload(locator):
    context, store = _context(), _store()
    candidate = SimpleNamespace(
        tenant_id=context.company_id,
        pdf_bytes=PDF,
        public_id="valid-public-id-12345",
        sha256_hex=sha256(PDF).hexdigest(),
        verification_url=locator,
    )
    with patch("services.document_issuance_immutable_staging.settings") as settings, \
         patch("services.document_issuance_immutable_staging.scan_upload", return_value="clean"), \
         patch("services.document_issuance_immutable_staging.prepare_stamped_document_candidate",
               return_value=candidate):
        settings.MALWARE_SCAN_ENABLED = True
        settings.MALWARE_SCAN_FAIL_CLOSED = True
        with pytest.raises(ValueError, match="QR locator"):
            _stage(context, store)
    store.put_locked_pdf.assert_not_called()


def test_incomplete_stamp_is_rejected_before_rendering_or_locking():
    context, store = _context(), _store()
    context.company.email = ""
    with patch("services.document_issuance_immutable_staging.settings") as settings, \
         patch("services.document_issuance_immutable_staging.prepare_stamped_document_candidate") as render, \
         patch("services.document_issuance_immutable_staging.scan_upload") as scan:
        settings.MALWARE_SCAN_ENABLED = True
        settings.MALWARE_SCAN_FAIL_CLOSED = True
        with pytest.raises(ValueError, match="company email"):
            _stage(context, store)
    render.assert_not_called()
    scan.assert_not_called()
    store.put_locked_pdf.assert_not_called()


def test_stamp_mutation_during_pdf_rendering_prevents_locked_upload():
    context, store = _context(), _store()

    def render(**kwargs):
        context.company.name = "Unexpected Updated Company"
        return SimpleNamespace(
            tenant_id=context.company_id, pdf_bytes=PDF,
            public_id="valid-public-id-12345",
            sha256_hex=sha256(PDF).hexdigest(),
            verification_url="https://verify.example.test/verify/valid-public-id-12345",
        )

    with patch("services.document_issuance_immutable_staging.settings") as settings, \
         patch("services.document_issuance_immutable_staging.scan_upload", return_value="clean") as scan, \
         patch("services.document_issuance_immutable_staging.prepare_stamped_document_candidate",
               side_effect=render):
        settings.MALWARE_SCAN_ENABLED = True
        settings.MALWARE_SCAN_FAIL_CLOSED = True
        with pytest.raises(PermissionError, match="changed while rendering"):
            _stage(context, store)
    assert scan.call_count == 1
    store.put_locked_pdf.assert_not_called()


def test_unapproved_stamp_is_denied_before_any_scan_render_or_upload():
    context, store = _context(), _store()
    with patch("services.document_issuance_immutable_staging.settings") as settings, \
         patch("services.document_issuance_immutable_staging.lookup_approved_stamp_from_database",
               side_effect=PermissionError("No authoritative stamp approval")) as approval, \
         patch("services.document_issuance_immutable_staging.scan_upload") as scan, \
         patch("services.document_issuance_immutable_staging.prepare_stamped_document_candidate") as render:
        settings.MALWARE_SCAN_ENABLED = True
        settings.MALWARE_SCAN_FAIL_CLOSED = True
        with pytest.raises(PermissionError, match="No authoritative"):
            _stage(context, store)
    approval.assert_called_once()
    render.assert_not_called()
    scan.assert_not_called()
    store.put_locked_pdf.assert_not_called()


def test_stamp_revoked_while_scanning_final_pdf_prevents_locked_upload():
    context, store = _context(), _store()
    candidate = SimpleNamespace(
        tenant_id=context.company_id, pdf_bytes=PDF,
        public_id="valid-public-id-12345", sha256_hex=sha256(PDF).hexdigest(),
        verification_url="https://verify.example.test/verify/valid-public-id-12345",
    )
    with patch("services.document_issuance_immutable_staging.settings") as settings, \
         patch("services.document_issuance_immutable_staging.lookup_approved_stamp_from_database",
               side_effect=[None, PermissionError("stamp approval revoked")]) as approval, \
         patch("services.document_issuance_immutable_staging.scan_upload",
               return_value="clean") as scan, \
         patch("services.document_issuance_immutable_staging.prepare_stamped_document_candidate",
               return_value=candidate):
        settings.MALWARE_SCAN_ENABLED = True
        settings.MALWARE_SCAN_FAIL_CLOSED = True
        with pytest.raises(PermissionError, match="revoked"):
            _stage(context, store)
    assert approval.call_count == 2
    assert scan.call_count == 2
    store.put_locked_pdf.assert_not_called()


def test_stamp_version_is_required_before_database_or_storage_access():
    context, store = _context(), _store()
    with patch("services.document_issuance_immutable_staging.settings") as settings, \
         patch("services.document_issuance_immutable_staging.lookup_approved_stamp_from_database") as approval:
        settings.MALWARE_SCAN_ENABLED = True
        settings.MALWARE_SCAN_FAIL_CLOSED = True
        with pytest.raises(ValueError, match="configuration version"):
            stage_locked_document_candidate(
                context=context, source_pdf=PDF,
                trusted_verification_origin="https://verify.example.test",
                store=store, db=Mock(), stamp_configuration_version=0,
            )
    approval.assert_not_called()
    store.put_locked_pdf.assert_not_called()
