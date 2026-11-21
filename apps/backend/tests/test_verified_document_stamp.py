"""Security regressions for backend tenant PDF stamping.

These tests intentionally do not call an issuance endpoint: the stamp is not
authoritative until a real immutable tenant-scoped database record is committed.
"""
from datetime import datetime, timezone
from io import BytesIO

import pytest
from reportlab.pdfgen import canvas

from services.verified_document_stamp import (
    DocumentStampError, StampCompany, prepare_stamped_pdf,
    sha256_pdf, verify_exact_pdf,
)


def _company(tenant="tenant-a"):
    return StampCompany(
        tenant_id=tenant, name="Example Finance (Pty) Ltd",
        registration_number="REG-123", address="Main Road, Maseru, Lesotho",
        phone="+266 50000000", email="example@example.org",
    )


def _pdf():
    output = BytesIO()
    document = canvas.Canvas(output)
    document.drawString(70, 700, "Original confidential document")
    document.save()
    return output.getvalue()


def _stamp(data=None, company=None, public_id=None, origin="https://verify.example.org"):
    return prepare_stamped_pdf(
        data if data is not None else _pdf(),
        company=company or _company(),
        public_id=public_id or "x" * 32,
        verification_origin=origin,
        issued_at=datetime(2026, 11, 17, tzinfo=timezone.utc),
    )


def test_pdf_has_separate_stamp_page_and_exact_hash():
    from pypdf import PdfReader

    original = _pdf()
    final, digest = _stamp(original)
    assert len(PdfReader(BytesIO(original)).pages) == 1
    assert len(PdfReader(BytesIO(final)).pages) == 2
    assert verify_exact_pdf(final, digest)
    assert sha256_pdf(final) == digest
    assert "COMPANY DOCUMENT STAMP" in PdfReader(BytesIO(final)).pages[-1].extract_text()
    assert "REG-123" in PdfReader(BytesIO(final)).pages[-1].extract_text()


def test_byte_mutation_fails_verification_even_with_same_document_id():
    final, digest = _stamp()
    assert not verify_exact_pdf(final + b"altered", digest)
    assert not verify_exact_pdf(final, "0" * 64)


@pytest.mark.parametrize("url", [
    "http://verify.example.org",
    "https://verify.example.org/fake",
    "https://user:password@verify.example.org",
    "https://verify.example.org?next=evil",
    "https://verify.example.org#frag",
])
def test_untrusted_verification_origins_fail_closed(url):
    with pytest.raises(DocumentStampError):
        _stamp(origin=url)


def test_short_predictable_id_rejected():
    with pytest.raises(DocumentStampError):
        _stamp(public_id="1234")


def test_incomplete_tenant_identity_rejected():
    incomplete = StampCompany("tenant-b", "Example", "", "", "", "")
    with pytest.raises(DocumentStampError):
        _stamp(company=incomplete)


def test_bad_and_empty_pdf_rejected():
    for invalid in (b"", b"not a pdf", b"%PDF-this is not a pdf"):
        with pytest.raises(DocumentStampError):
            _stamp(data=invalid)


def test_requires_timezone_aware_date():
    with pytest.raises(DocumentStampError):
        prepare_stamped_pdf(
            _pdf(), company=_company(), public_id="x" * 32,
            verification_origin="https://verify.example.org",
            issued_at=datetime(2026, 11, 17),
        )
