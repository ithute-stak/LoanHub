from pathlib import Path

PAGE = Path(__file__).resolve().parents[2] / "frontend/app/(dashboard)/company/origination/decision-centre/[applicationId]/page.tsx"


def test_owner_topup_actions_do_not_bypass_approval_or_disbursement():
    source = PAGE.read_text()
    assert 'activeRole === "company_owner"' in source
    assert 'application.application_type === "top_up"' in source
    assert "Verify terms and assess affordability" in source
    assert "Review owner decision" in source
    assert "Contract and authorized disbursement" in source
    assert "Disbursement unavailable until loan creation and signing" in source
    assert "originationApi.submit(application.id)" not in source
    assert "disburseLoan(" not in source


def test_missing_assessment_does_not_appear_as_failed_loan():
    source = PAGE.read_text()
    assert 'const missingAssessment = !assessment && decision === "not_loanable"' in source
    assert '"ASSESSMENT REQUIRED"' in source
