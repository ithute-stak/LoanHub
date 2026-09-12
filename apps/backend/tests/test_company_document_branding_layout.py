from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]


def source(relative: str) -> str:
    return (BACKEND_ROOT / relative).read_text(encoding="utf-8")


def test_shared_branding_service_resolves_system_and_company_logos() -> None:
    text = source("services/document_branding_service.py")
    assert "class CompanyDocumentBranding" in text
    assert "system_logo=_system_logo_bytes()" in text
    assert "company_logo=_company_logo_bytes(db, company_id)" in text
    assert 'RIGHT_LOGO_CATEGORIES = {"company_logo_right", "company_logo_secondary"}' in text
    assert 'LEFT_LOGO_CATEGORIES = {"company_logo_left", "company_logo", "company_brand_logo"}' in text


def test_contract_header_uses_shared_three_column_branding() -> None:
    text = source("services/contract_service.py")
    assert "get_company_document_branding" in text
    assert "branding.system_logo" in text
    assert "branding.company_logo" in text
    assert "branding.company_name" in text
    assert "branding.identity_line" in text
    assert "branding.contact_line" in text
    assert "branding.address_line" in text


def test_receipt_header_uses_same_branding_source() -> None:
    text = source("services/receipt_service.py")
    assert "get_company_document_branding" in text
    assert "branding.system_logo" in text
    assert "branding.company_logo" in text
    assert "centre_lines" in text
    assert "generate_payment_receipt_pdf" in text
    assert "ensure_pdf: bool = True" in text
