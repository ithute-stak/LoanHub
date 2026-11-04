"""Guardrails for Wacom test-only mode in the real company loan modal."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
LOANS = ROOT / "apps/frontend/app/(dashboard)/company/loans/page.tsx"
DIALOG = ROOT / "apps/frontend/components/ui/custom-dialog.tsx"


def test_real_company_contract_modal_renders_wacom_preview_only():
    text = LOANS.read_text()
    assert 'import {ContractPadPreflight}' in text
    assert 'value="wacom_preview">Wacom STU-540 (test preview only)' in text
    assert 'signatureMethod === "wacom_preview" ? <div' in text
    assert '<ContractPadPreflight' in text
    assert 'signatureMethod !== "email_otp" && signatureMethod !== "wacom_preview"' in text
    assert '!selectedContract.company_signed_at && signatureMethod !== "wacom_preview"' in text


def test_signing_api_handlers_refuse_preview_method():
    text = LOANS.read_text()
    assert '(signatureMethod === "email_otp" || signatureMethod === "wacom_preview")' in text
    assert 'if (!selectedContract || signatureMethod === "wacom_preview") return;' in text
    assert 'onCapture=' not in text
    assert 'No Wacom pen strokes are transmitted to the server.' not in text or 'no Wacom pen strokes are transmitted to the server.' in text


def test_contract_dialog_header_does_not_overlay_brand_logo():
    text = LOANS.read_text()
    assert 'contentClassName="sm:max-w-3xl" solidHeader' in text
    dialog = DIALOG.read_text()
    assert "solidHeader?: boolean" in dialog
    assert "!solidHeader ? <Image" in dialog
