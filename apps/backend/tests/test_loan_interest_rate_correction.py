"""Loan rate amendments must be quoted, restricted and audited."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API = (ROOT / "routers/loans.py").read_text()
UI = (ROOT.parent / "frontend/app/(dashboard)/company/loans/page.tsx").read_text()
CORRECTION = API.split("class LoanRateCorrectionRequest", 1)[1].split('@router.post("/{loan_id}/installments/{installment_id}/payments"', 1)[0]


def test_only_company_owner_can_preview_and_apply():
    assert CORRECTION.count('require_tenant_roles(context, {UserRole.COMPANY_OWNER})') == 2
    assert "confirm: bool = False" in CORRECTION
    assert "signed_amendment_reference" in CORRECTION
    assert 'action="loan.interest_rate_corrected"' in CORRECTION
    assert '"reason": payload.reason' in CORRECTION


def test_financial_and_provider_guards():
    for check in ("loan.amount_paid", "loan.cdas_collection_enabled",
                  "CDASDeductionMandate.loan_id == loan.id", "item.allocations",
                  "item.status != InstallmentStatus.PENDING",
                  "with_for_update().one()"):
        assert check in CORRECTION
    assert "calculate_loan_terms(" in CORRECTION
    assert "loan.total_repayable = Decimal" in CORRECTION
    assert "loan.balance = loan.total_repayable" in CORRECTION


def test_ui_prompts_for_before_after_and_signed_evidence():
    assert "Correct loan interest rate" in UI
    assert "Preview before / after" in UI
    assert "Signed borrower amendment reference" in UI
    assert "Apply audited correction" in UI
