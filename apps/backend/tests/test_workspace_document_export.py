import sys
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
