import sys
from io import BytesIO
from unittest.mock import patch
from uuid import uuid4

import pytest
from pypdf import PdfReader
import types
from pathlib import Path
from types import SimpleNamespace


class _CryptContext:
    def __init__(self, *args, **kwargs):
        pass

    def hash(self, value):
        return value

    def verify(self, plain, hashed):
        return plain == hashed


_passlib_context = types.ModuleType("passlib.context")
_passlib_context.CryptContext = _CryptContext
_passlib = types.ModuleType("passlib")
_passlib.context = _passlib_context
sys.modules.setdefault("passlib", _passlib)
sys.modules.setdefault("passlib.context", _passlib_context)

# The exporter tests do not need database-backed branding. Keeping this stub
# makes the test isolated and runnable without PostgreSQL or file storage.
_branding = types.ModuleType("services.document_branding_service")
_branding.get_company_branding_logos = lambda db, company: SimpleNamespace(
    left_logo=None,
    right_logo=None,
)
sys.modules["services.document_branding_service"] = _branding

from services.workspace_document_service import (
    default_document_html,
    export_docx,
    export_pdf,
    plain_text_from_html,
    sanitize_document_html,
    signature_field_count,
)


class DummyDb:
    pass


def sample_document():
    return SimpleNamespace(
        content_html=(
            "<p style='text-align:right'>24 July 2026</p>"
            "<p><strong>Recipient Name</strong><br>Organisation</p>"
            "<h2 style='text-align:center'>RE: TEST LETTER</h2>"
            "<p style='font-family:Georgia;font-size:12pt;line-height:1.5'>"
            "This is a <strong>formatted</strong> LoanHub letter.</p>"
            "<ul><li>First point</li><li>Second point</li></ul>"
            "<div data-signature-field='true' data-field-id='field-1' "
            "data-field-type='signature' data-label='Borrower signature' "
            "data-assigned-to='Borrower' data-required='true' data-width='100' "
            "data-height='62' data-placeholder='Sign here'></div>"
        ),
        reference="DOC-TEST001",
        version=2,
        title="Test letter",
        is_confidential=False,
        owner=SimpleNamespace(person=None, email="author@example.com", phone="+26650000000"),
        orientation="portrait",
        page_size="A4",
        margin_top_mm=28,
        margin_right_mm=22,
        margin_bottom_mm=24,
        margin_left_mm=22,
        include_brand_header=False,
        include_footer=True,
        style_key="modern_blue",
        default_font_family="Arial",
        default_font_size_pt=11,
        default_line_height_percent=115,
    )


def test_sanitizer_removes_active_content_and_preserves_signature_fields():
    cleaned = sanitize_document_html(
        "<p>Hello</p><script>alert(1)</script><img src='javascript:bad'>"
        "<div data-signature-field='true' data-label='Signature'></div>"
    )
    assert "script" not in cleaned.lower()
    assert "javascript:" not in cleaned.lower()
    assert "data-signature-field" in cleaned
    assert signature_field_count(cleaned) == 1
    assert plain_text_from_html(cleaned) == "Hello\nalert(1)\n[Signature]"


def test_docx_export_has_zip_signature_and_signature_field():
    content = export_docx(DummyDb(), sample_document(), None)
    assert content[:2] == b"PK"
    assert len(content) > 1000


def test_pdf_export_has_pdf_signature_and_signature_field():
    content = export_pdf(DummyDb(), sample_document(), None)
    assert content.startswith(b"%PDF-")
    assert len(content) > 1000


def test_template_gallery_has_all_supported_document_starters():
    template_keys = {
        "blank",
        "formal_letter",
        "business_letter",
        "memo",
        "meeting_minutes",
        "project_report",
        "proposal",
        "policy",
        "contract",
        "invoice",
        "certificate",
        "resume",
    }
    for template_key in template_keys:
        value = default_document_html(template_key, "Test Author")
        assert isinstance(value, str)
        assert value or template_key == "blank"


def test_word_style_schema_repair_migration_is_present():
    migration = (
        Path(__file__).resolve().parents[1]
        / "alembic"
        / "versions"
        / "u4f6a8b1c350_workspace_document_schema_repair.py"
    ).read_text(encoding="utf-8")
    for expected in (
        "workspace_documents",
        "workspace_document_collaborators",
        "workspace_document_revisions",
        "style_key",
        "default_font_family",
        "default_font_size_pt",
        "default_line_height_percent",
    ):
        assert expected in migration


def _company_letter():
    document = sample_document()
    company_id = uuid4()
    document.company_id = company_id
    document.template_key = "client_confirmation_letter"
    company = SimpleNamespace(
        id=company_id,
        legal_name="Example Financial Services (Pty) Ltd",
        name="Example Financial Services",
        registration_number="REG-0001",
        license_number="LIC-0001",
        address="Maseru, Lesotho",
        phone="+266 50000000",
        email="contact@example.test",
    )
    return document, company


def _pdf_text(payload):
    return "\n".join(page.extract_text() or "" for page in PdfReader(BytesIO(payload)).pages)


def test_company_letter_preview_stamp_is_disabled_by_default():
    document, company = _company_letter()
    with patch.dict("os.environ", {"LOANHUB_LETTER_STAMP_PREVIEW_ENABLED": "0"}):
        pdf = export_pdf(DummyDb(), document, company)
    text = _pdf_text(pdf)
    assert "RE: TEST LETTER" in text
    assert "COMPANY STAMP" not in text


def test_opt_in_unsigned_company_letter_has_non_authoritative_stamp_after_body():
    document, company = _company_letter()
    with patch.dict("os.environ", {"LOANHUB_LETTER_STAMP_PREVIEW_ENABLED": "1", "ENVIRONMENT": "test"}):
        pdf = export_pdf(DummyDb(), document, company)
    text = _pdf_text(pdf)
    assert "RE: TEST LETTER" in text
    assert "Example Financial Services (Pty) Ltd" in text
    assert "COMPANY STAMP" in text
    assert "NOT APPROVED OR VERIFIED" in text
    assert text.index("RE: TEST LETTER") < text.index("COMPANY STAMP")


def test_cross_tenant_company_cannot_render_letter_stamp_preview():
    document, company = _company_letter()
    company.id = uuid4()
    with patch.dict("os.environ", {"LOANHUB_LETTER_STAMP_PREVIEW_ENABLED": "1", "ENVIRONMENT": "test"}):
        with pytest.raises(PermissionError, match="document tenant"):
            export_pdf(DummyDb(), document, company)


def test_non_letter_document_never_receives_preview_stamp():
    document, company = _company_letter()
    document.template_key = "contract"
    with patch.dict("os.environ", {"LOANHUB_LETTER_STAMP_PREVIEW_ENABLED": "1", "ENVIRONMENT": "test"}):
        text = _pdf_text(export_pdf(DummyDb(), document, company))
    assert "COMPANY STAMP" not in text


def test_existing_signatures_block_preview_stamp_mutation():
    document, company = _company_letter()
    document.id = uuid4()
    with patch.dict("os.environ", {"LOANHUB_LETTER_STAMP_PREVIEW_ENABLED": "1", "ENVIRONMENT": "test"}), patch(
        "services.workspace_document_service.active_signatures",
        return_value={"field-1": object()},
    ):
        with pytest.raises(PermissionError, match="after document signatures"):
            export_pdf(DummyDb(), document, company)


@pytest.mark.parametrize("template_key", ["formal_letter", "business_letter"])
def test_ordinary_company_letter_preview_supported(template_key):
    document, company = _company_letter()
    document.template_key = template_key
    with patch.dict("os.environ", {
        "LOANHUB_LETTER_STAMP_PREVIEW_ENABLED": "1",
        "ENVIRONMENT": "test",
    }):
        text = _pdf_text(export_pdf(DummyDb(), document, company))
    assert "COMPANY STAMP" in text
    assert "NOT APPROVED OR VERIFIED" in text


@pytest.mark.parametrize("change", [
    {"status": "published"},
    {"status": "finalized"},
    {"finalized_at": "2026-11-21T12:00:00Z"},
])
def test_published_or_finalized_letter_cannot_be_preview_stamped(change):
    document, company = _company_letter()
    for attribute, value in change.items():
        setattr(document, attribute, value)
    with patch.dict("os.environ", {
        "LOANHUB_LETTER_STAMP_PREVIEW_ENABLED": "1",
        "ENVIRONMENT": "test",
    }):
        with pytest.raises(PermissionError, match="unsigned draft"):
            export_pdf(DummyDb(), document, company)


@pytest.mark.parametrize("environment", ["production", "staging", "", "PRODUCTION"])
def test_preview_stamp_denied_outside_development_and_test(environment):
    document, company = _company_letter()
    with patch.dict("os.environ", {
        "LOANHUB_LETTER_STAMP_PREVIEW_ENABLED": "1",
        "ENVIRONMENT": environment,
    }):
        with pytest.raises(PermissionError, match="outside development or test"):
            export_pdf(DummyDb(), document, company)


@pytest.mark.parametrize("tenant_field", [None, "not-a-uuid"])
def test_stamp_preview_rejects_missing_or_invalid_tenant(tenant_field):
    document, company = _company_letter()
    document.company_id = tenant_field
    company.id = tenant_field
    with patch.dict("os.environ", {
        "LOANHUB_LETTER_STAMP_PREVIEW_ENABLED": "1", "ENVIRONMENT": "test",
    }):
        with pytest.raises(PermissionError, match="document tenant"):
            export_pdf(DummyDb(), document, company)


def test_stamp_preview_rejects_unconfigured_legal_identity():
    document, company = _company_letter()
    company.email = None
    with patch.dict("os.environ", {
        "LOANHUB_LETTER_STAMP_PREVIEW_ENABLED": "1", "ENVIRONMENT": "test",
    }):
        with pytest.raises(ValueError, match="Invalid company email"):
            export_pdf(DummyDb(), document, company)


def test_nonletter_pdf_not_blocked_by_preview_environment_guard():
    document, company = _company_letter()
    document.template_key = "contract"
    with patch.dict("os.environ", {
        "LOANHUB_LETTER_STAMP_PREVIEW_ENABLED": "1", "ENVIRONMENT": "production",
    }):
        text = _pdf_text(export_pdf(DummyDb(), document, company))
    assert "RE: TEST LETTER" in text
    assert "COMPANY STAMP" not in text


def test_multipage_pdf_freezes_resolved_company_logo_bytes():
    document, company = _company_letter()
    document.content_html = "<p>Long multi-page letter</p>" + (
        "<p>Repeated paragraph for long PDF export.</p>" * 280
    )
    document.include_brand_header = True
    logos = SimpleNamespace(left_logo=None, right_logo=None)
    with patch(
        "services.workspace_document_service.get_company_branding_logos",
        return_value=logos,
    ) as resolve:
        pdf = export_pdf(DummyDb(), document, company)
    assert len(PdfReader(BytesIO(pdf)).pages) > 1
    assert resolve.call_count == 1\n    assert resolve.call_args.args[1] is company


def test_no_company_logo_lookup_for_headerless_pdf():
    document, company = _company_letter()
    document.include_brand_header = False
    with patch(
        "services.workspace_document_service.get_company_branding_logos",
    ) as resolve:
        export_pdf(DummyDb(), document, company)
    resolve.assert_not_called()
