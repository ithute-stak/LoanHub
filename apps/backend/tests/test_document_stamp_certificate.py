from datetime import datetime, timezone
from io import BytesIO
from uuid import uuid4

import pytest
from pypdf import PdfReader
from reportlab.pdfgen import canvas

from services.document_stamp_certificate import TenantStamp, render_tenant_stamp_certificate


def source_pdf():
    out = BytesIO()
    c = canvas.Canvas(out)
    c.drawString(40, 750, "Confidential sample contract")
    c.save()
    return out.getvalue()


def sample_stamp(tenant_id):
    return TenantStamp(
        tenant_id=tenant_id,
        legal_name="Example Financial Services (Pty) Ltd",
        registration_number="2026/123",
        license_number="ML-1",
        address="Kingsway Road, Maseru, Lesotho",
        phones="+266 50000000",
        email="example@example.test",
    )


def render(*, stamp=None, expected_tenant_id=None, pdf=None, url=None):
    tenant = expected_tenant_id or uuid4()
    return render_tenant_stamp_certificate(
        source_pdf=source_pdf() if pdf is None else pdf,
        stamp=stamp or sample_stamp(tenant),
        public_id="test-reference-a93f72b4",
        verification_url=url or "https://verify.example.test/verify/test-reference-a93f72b4",
        issued_at=datetime(2026, 11, 17, 10, 0, tzinfo=timezone.utc),
        expected_tenant_id=tenant,
        trusted_verification_host="verify.example.test",
    )


def test_certificate_appends_page_without_changing_original_page_text():
    tenant = uuid4()
    source = source_pdf()
    result = render(stamp=sample_stamp(tenant), expected_tenant_id=tenant, pdf=source)
    before = PdfReader(BytesIO(source))
    after = PdfReader(BytesIO(result))
    assert len(after.pages) == len(before.pages) + 1
    assert "Confidential sample contract" in after.pages[0].extract_text()
    text = after.pages[-1].extract_text()
    assert "Example Financial Services" in text
    assert "test-reference-a93f72b4" in text
    assert "NOT a cryptographic PDF signature" in text


def test_cross_tenant_stamp_fails_closed():
    with pytest.raises(PermissionError):
        render(stamp=sample_stamp(uuid4()), expected_tenant_id=uuid4())


@pytest.mark.parametrize("url", [
    "http://verify.example.test/verify/test-reference-a93f72b4",
    "https://attacker.test/verify/test-reference-a93f72b4",
    "https://verify.example.test/verify/other-reference",
    "https://user:password@verify.example.test/verify/test-reference-a93f72b4",
    "https://verify.example.test/verify/test-reference-a93f72b4?secret=yes",
])
def test_unacceptable_verification_urls_rejected(url):
    with pytest.raises(ValueError):
        render(url=url)


def test_invalid_pdf_fails_closed():
    with pytest.raises(ValueError):
        render(pdf=b"%PDF-invalid")


def test_required_company_fields_cannot_be_blank():
    stamp = sample_stamp(uuid4())
    with pytest.raises(ValueError):
        TenantStamp(
            tenant_id=stamp.tenant_id, legal_name=" ",
            address="here", phones="1", email="user@example.test",
        ).validate()
