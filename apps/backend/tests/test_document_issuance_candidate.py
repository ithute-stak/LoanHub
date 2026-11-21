from datetime import datetime, timezone
from io import BytesIO
from types import SimpleNamespace
from uuid import uuid4

import pytest
from reportlab.pdfgen import canvas
from pypdf import PdfReader

from services.document_issuance_candidate import prepare_stamped_document_candidate
from services.document_issuance_integrity import pdf_fingerprint


def _pdf():
    out = BytesIO()
    c = canvas.Canvas(out)
    c.drawString(50, 700, "Sample client document")
    c.save()
    return out.getvalue()


def _company(tenant_id):
    return SimpleNamespace(
        id=tenant_id, name="Sample Financial Services (Pty) Ltd",
        registration_number="REG-2026", license_number="LIC-2026",
        address="Maseru, Lesotho", phone="+266 50000000",
        email="sample@example.test",
    )


def _candidate(tenant, company=None, **overrides):
    opts = dict(
        source_pdf=_pdf(), company=company or _company(tenant),
        authenticated_tenant_id=tenant,
        issued_at=datetime(2026, 11, 17, tzinfo=timezone.utc),
        trusted_verification_origin="https://verify.example.test",
        public_id="document-issue-abc123456",
    )
    opts.update(overrides)
    return prepare_stamped_document_candidate(**opts)


def test_certificate_qr_reference_and_digest_use_same_final_bytes():
    tenant = uuid4()
    result = _candidate(tenant)
    assert result.tenant_id == tenant
    assert result.public_id == "document-issue-abc123456"
    assert result.verification_url == "https://verify.example.test/verify/document-issue-abc123456"
    assert result.sha256_hex == pdf_fingerprint(result.pdf_bytes)
    pages = PdfReader(BytesIO(result.pdf_bytes)).pages
    assert len(pages) == 2
    assert "Sample client document" in pages[0].extract_text()
    assert "document-issue-abc123456" in pages[1].extract_text()


def test_different_tenant_cannot_use_other_company_identity():
    with pytest.raises(PermissionError):
        _candidate(uuid4(), company=_company(uuid4()))


@pytest.mark.parametrize("origin", [
    "http://verify.example.test",
    "https://verify.example.test/path",
    "https://verify.example.test?token=secret",
    "https://someone:secret@verify.example.test",
])
def test_reject_unsafe_verification_origin(origin):
    with pytest.raises(ValueError):
        _candidate(uuid4(), trusted_verification_origin=origin)


def test_invalid_preallocated_id_fails_closed():
    with pytest.raises(ValueError):
        _candidate(uuid4(), public_id="../other-doc")
