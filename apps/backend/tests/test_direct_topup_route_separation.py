"""Direct top-up navigation must never return to the new-loan origination wizard."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / "frontend"
LOANS = (ROOT / "app/(dashboard)/company/loans/page.tsx").read_text(encoding="utf-8")
TOPUP = (ROOT / "app/(dashboard)/company/loans/top-up/page.tsx").read_text(encoding="utf-8")
WIZARD = (ROOT / "app/(dashboard)/company/origination/new/page.tsx").read_text(encoding="utf-8")
MARKETPLACE = (ROOT / "app/(dashboard)/company/marketplace/_components/internal-applications-workspace.tsx").read_text(encoding="utf-8")
DIALOG = (ROOT / "components/loans/compact-top-up-dialog.tsx").read_text(encoding="utf-8")


def test_existing_loan_topup_routes_directly_to_topup_workspace():
    assert "/company/loans/top-up?loan=" in LOANS
    assert "/company/loans/top-up?application=" in LOANS
    assert "router.push(`/company/origination/new?application=${existing.id}`)" not in LOANS
    assert "<CompactTopUpDialog" not in LOANS


def test_topup_has_a_real_dedicated_page_with_repayment_preview_and_submission():
    assert "function TopUpWorkspace()" in TOPUP
    assert "<CompactTopUpDialog loan={loan} inline" in TOPUP
    assert "originationApi.submit(application.id)" in TOPUP
    assert "originationApi.approveTopUpException(application.id" in TOPUP
    assert "/company/marketplace?workspace=applications" in TOPUP
    assert "originationApi.createCompactTopUp(" in DIALOG
    assert "/origination/loans/${loan.id}/top-up-calculation-preview" in DIALOG
    assert "if (inline)" in DIALOG


def test_new_loan_wizard_never_offers_topup_selection():
    assert ">Top-up existing loan</p>" not in WIZARD
    assert "Use saved records & review top-up" not in WIZARD
    assert "No, just offer top-up" not in WIZARD
    assert 'router.replace(`/company/loans/top-up?application=' in WIZARD
    assert 'router.replace(requestedLoanId ? `/company/loans/top-up?loan=' in WIZARD


def test_pending_topup_drafts_use_direct_workspace():
    assert 'selected.application_type === "top_up" ? `/company/loans/top-up?application=' in MARKETPLACE
