from pathlib import Path

PAGE = Path(__file__).resolve().parents[2] / "frontend/app/(dashboard)/company/loans/page.tsx"


def test_portfolio_resumes_existing_topup_application():
    source = PAGE.read_text()
    assert "originationApi.listApplications()" in source
    assert 'application.application_type === "top_up"' in source
    assert '["draft", "submitted", "under_review"].includes(application.status)' in source
    assert "item.parent_loan_id === selectedLoan.id" in source
    assert "Continue existing top-up" in source
    assert "router.push(`/company/origination/new?application=${existing.id}`)" in source


def test_portfolio_does_not_change_financial_balance_before_disbursement():
    source = PAGE.read_text()
    assert "setTopUpLoan(selectedLoan)" in source
    assert "originationApi.listApplications()" in source
    assert "setLoans((rows) => rows.map" in source
