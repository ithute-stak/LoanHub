from pathlib import Path
import sys
import types
from types import SimpleNamespace

_branding = types.ModuleType("services.document_branding_service")
_branding.get_company_branding_logos = lambda db, company: SimpleNamespace(
    left_logo=None,
    right_logo=None,
)
sys.modules["services.document_branding_service"] = _branding

from services.workspace_document_service import default_document_html


BACKEND_ROOT = Path(__file__).resolve().parents[1]
PROJECT_APPS = BACKEND_ROOT.parent


def source(relative: str) -> str:
    return (BACKEND_ROOT / relative).read_text(encoding="utf-8")


def frontend_source(relative: str) -> str:
    return (PROJECT_APPS / "frontend" / relative).read_text(encoding="utf-8")


def test_customer_letter_templates_merge_verified_values():
    context = {
        "date": "28 July 2026",
        "client_name": "Test Client",
        "client_title": "Ms",
        "client_national_id": "123456789012",
        "company_name": "Example Financial Services",
        "signer_name": "Test Manager",
        "signer_title": "Manager",
        "loan_reference": "LB-TEST-001",
        "loan_balance": "LSL 1,250.00",
        "loan_installment_amount": "LSL 250.00",
        "company_bank_accounts": "Example Bank - Account 123",
    }

    confirmation = default_document_html(
        "client_confirmation_letter",
        "Fallback Sender",
        context,
    )
    paid_up = default_document_html("paid_up_letter", "Fallback Sender", context)
    settlement = default_document_html("settlement_letter", "Fallback Sender", context)

    assert "TEST CLIENT" in confirmation
    assert "123456789012" in confirmation
    assert "Example Financial Services" in confirmation
    assert "Test Manager" in confirmation

    assert "LB-TEST-001" in paid_up
    assert "settled that debt in full" in paid_up

    assert "LSL 1,250.00" in settlement
    assert "LSL 250.00" in settlement
    assert "Example Bank - Account 123" in settlement
    assert "VALID FOR 30 DAYS" in settlement


def test_customer_letter_service_has_financial_safety_guards():
    text = source("services/client_document_template_service.py")
    assert "A no-arrears confirmation cannot be generated" in text
    assert "A paid-up letter can only be generated after the ledger balance reaches zero" in text
    assert "This loan is already settled. Use the Paid-Up Letter template instead." in text
    assert "The selected loan currently has arrears" in text


def test_customer_letters_force_company_branding():
    text = source("routers/workspace_documents.py")
    assert 'visibility="company" if is_client_letter else payload.visibility' in text
    assert "include_brand_header=True if is_client_letter" in text
    assert "brand_logo_asset_id=None if is_client_letter" in text

    workspace = source("services/workspace_document_service.py")
    assert "get_company_branding_logos" in workspace
    assert "logos.right_logo" in workspace


def test_loan_documents_and_payment_slips_use_shared_company_branding():
    loan_documents = source("services/loan_document_service.py")
    pdf_system = source("services/pdf_design_system.py")
    receipts = source("services/receipt_service.py")

    assert "DocumentContext" in loan_documents
    assert "get_company_branding_logos" in pdf_system
    assert "get_company_document_branding" in receipts
    assert "branding.company_logo" in receipts


def test_company_client_screen_exposes_letters_action_and_gallery_templates():
    clients_page = frontend_source("app/(dashboard)/company/clients/page.tsx")
    studio = frontend_source("components/documents/document-studio-home.tsx")

    assert "/company/documents?client=${client.id}" in clients_page
    assert ">Letters<" in clients_page

    for key in (
        "client_confirmation_letter",
        "good_standing_confirmation_letter",
        "paid_up_letter",
        "settlement_letter",
    ):
        assert key in studio
    assert "Create auto-filled letter" in studio
