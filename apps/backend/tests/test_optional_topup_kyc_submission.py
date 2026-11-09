"""KYC verification is optional for top-up submission, but existing independent controls remain."""
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
FRONTEND = BACKEND.parent / "frontend"
ORIGINATION = (BACKEND / "routers/origination.py").read_text(encoding="utf-8")
DIRECT_TOPUP = (FRONTEND / "app/(dashboard)/company/loans/top-up/page.tsx").read_text(encoding="utf-8")


def test_topup_can_reach_management_review_without_kyc_verification():
    submit = ORIGINATION.split("def submit_application(", 1)[1].split(
        '@router.post("/loans/{loan_id}/contract"', 1
    )[0]
    assert 'application.application_type != "top_up" and policy.require_kyc_verified' in submit
    assert 'if policy.require_kyc_verified and (not profile["kyc"]' not in submit
    assert 'application.status = "submitted"' in submit


def test_new_loan_kyc_policy_and_topup_independent_controls_are_preserved():
    submit = ORIGINATION.split("def submit_application(", 1)[1].split(
        '@router.post("/loans/{loan_id}/contract"', 1
    )[0]
    assert 'profile["kyc"]["status"] != "verified"' in submit
    assert "enforce_duplicate_policy(" in submit
    assert "_require_cdas_payroll_profile(" in submit
    assert "top_up_exception_approved=bool(application.top_up_exception_approved)" in submit
    assert "KYC verification is optional when submitting a top-up" in DIRECT_TOPUP
    assert "management approval, contract and disbursement controls still apply" in DIRECT_TOPUP
