"""Guard against accidental CDAS mapping of one employee number to multiple borrowers."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_discovery_cross_checks_both_company_scoped_identity_sources():
    source = (ROOT / "routers/cdas_api.py").read_text()
    start = source.index("def _discover_employee_loan_for_review(")
    end = source.index('@router.post("/employees/registration-context")', start)
    body = source[start:end]
    assert "CDASPayrollProfile.company_id == company_id" in body
    assert "BorrowerEmploymentProfile.company_id == company_id" in body
    assert "borrower_ids = {p.borrower_id for p in profiles} | {row.borrower_id for row in employment}" in body
    assert "if len(borrower_ids) != 1:" in body
    assert "if profile is None or not profile.verified:" in body
    assert "ClientCompanyLoan.company_id == company_id" in body
    assert "No approved or active company loan found" in body


def test_real_registration_still_checks_verified_profile_and_affordability():
    source = (ROOT / "routers/cdas_api.py").read_text()
    assert 'elif not profile.verified:' in source
    assert "if payload.deduction_amount > affordability:" in source
    assert "if not payload.borrower_consent:" in source
