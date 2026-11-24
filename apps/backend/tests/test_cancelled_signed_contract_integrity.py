"""Regression guards for signed-document preservation after pre-payout loan cancellation."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CANCEL = (ROOT / "routers/loans.py").read_text()
ORIGINATION = (ROOT / "routers/origination.py").read_text()
CONTRACTS = (ROOT / "services/contract_service_base.py").read_text()
FRONTEND = (ROOT.parent / "frontend/app/(dashboard)/company/loans/page.tsx").read_text()


def test_cancellation_preserves_signatures_pdf_and_status():
    body = CANCEL.split("def cancel_approved_undisbursed_loan(", 1)[1].split("@router.", 1)[0]
    assert "loan.status = LoanStatus.CANCELLED" in body
    assert 'contract.status = "cancelled"' not in body
    assert "contract.borrower_signed_at =" not in body
    assert "contract.company_signed_at =" not in body
    assert "contract.pdf_file_id =" not in body
    assert "contract.contract_hash =" not in body


def test_legacy_cancelled_signed_contracts_render_as_signed():
    assert "fully_signed = bool(self.contract.borrower_signed_at and self.contract.company_signed_at)" in CONTRACTS
    assert 'confidentiality = "CONFIDENTIAL | " if fully_signed else "DRAFT | "' in CONTRACTS
    assert "if not fully_signed:" in CONTRACTS


def test_signed_or_cancelled_contracts_are_immutable():
    body = CONTRACTS.split("def regenerate_contract_pdf(", 1)[1].split("def refresh_contract_pdf_after_signature(", 1)[0]
    assert "contract.loan.status == LoanStatus.CANCELLED" in body
    assert "contract.borrower_signed_at or contract.company_signed_at or contract.locked_at" in body
    for action in ("borrower_sign_contract", "company_sign_contract"):
        body = ORIGINATION.split(f"def {action}(", 1)[1].split("@router.", 1)[0]
        assert "linked_loan.status == LoanStatus.CANCELLED" in body
        assert "assert_branch_scope(context, linked_loan.branch_id)" in body


def test_frontend_keeps_signed_record_and_does_not_offer_regeneration():
    assert 'setContracts(previous => previous.map(item => item.loan_id === result.id ? {...item, status: "cancelled"}' not in FRONTEND
    assert 'selectedContract.status === "cancelled"' in FRONTEND
    assert "!selectedContract.borrower_signed_at && !selectedContract.company_signed_at" in FRONTEND
    assert 'selectedContract.status !== "signed" && selectedContract.status !== "cancelled" && !selectedContract.borrower_signed_at && !selectedContract.company_signed_at ?' in FRONTEND
    assert 'selectedContract.status !== "signed" && selectedContract.status !== "cancelled" && !selectedContract.borrower_signed_at && !selectedContract.company_signed_at ?' in FRONTEND.split("Open PDF</LoadingButton>", 1)[1]
