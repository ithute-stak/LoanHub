from __future__ import annotations

from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate

from database.schemas.origination import ContractGenerateRequest
import services.contract_service as contract_service
from services.debit_order_mandate import build_debit_order_mandate


ROOT = Path(__file__).resolve().parents[3]
FRONTEND = ROOT / "apps" / "frontend"


def test_contract_generation_defaults_mandate_off_and_accepts_true():
    assert ContractGenerateRequest().include_mandate is False
    assert ContractGenerateRequest(include_mandate=True).include_mandate is True


def test_generate_contract_scopes_mandate_choice_to_the_current_generation(monkeypatch):
    seen: list[bool] = []
    sentinel = SimpleNamespace(id="contract")

    def fake_generate_contract(*args, **kwargs):
        seen.append(contract_service._active_include_mandate.get())
        return sentinel

    monkeypatch.setattr(contract_service, "_original_generate_contract", fake_generate_contract)

    result = contract_service.generate_contract(
        None,
        loan=SimpleNamespace(),
        requested_by_user_id=None,
        include_mandate=True,
    )

    assert result is sentinel
    assert seen == [True]
    assert contract_service._active_include_mandate.get() is False


def test_mandate_annexure_renders_from_frozen_contract_values():
    flowables = build_debit_order_mandate(
        {
            "agreement_date": "2026-09-26",
            "loan_reference": "LN-1001",
            "installment_amount": "1250.00",
            "first_payment_due": "2026-10-31",
            "preferred_payment_day": 31,
            "borrower": {
                "name": "Mpho Example",
                "physical_address": "Maseru, Lesotho",
            },
            "company": {
                "name": "Example Lender",
                "address": "Maseru, Lesotho",
            },
            "bank_account": {
                "account_holder": "Mpho Example",
                "bank_name": "Example Bank",
                "branch_code": "123456",
                "account_type": "savings",
            },
        },
        agreement_reference="CTR-1001",
        account_number="600012345678",
    )

    assert isinstance(flowables[0], PageBreak)
    assert isinstance(flowables[1], Paragraph)
    assert "AUTHORITY TO DEBIT ACCOUNT" in flowables[1].text

    output = BytesIO()
    document = SimpleDocTemplate(output, pagesize=A4)
    document.build([Paragraph("Base contract", getSampleStyleSheet()["BodyText"]), *flowables])
    pdf = output.getvalue()

    assert pdf.startswith(b"%PDF")
    assert len(pdf) > 2000


def test_frontend_generation_exposes_and_sends_optional_mandate_choice():
    api_source = (FRONTEND / "api" / "origination.ts").read_text(encoding="utf-8")
    print_source = (FRONTEND / "components" / "loans" / "loan-print-actions.tsx").read_text(encoding="utf-8")

    assert "includeMandate?: boolean" in api_source
    assert "include_mandate: resolvedIncludeMandate" in api_source
    assert "Include debit-order mandate" in print_source
    assert "checked={includeMandate}" in print_source
    assert "checked === true" in print_source
