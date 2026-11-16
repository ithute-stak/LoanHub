"""Legacy quarantine never identifies a loan by shared borrower identity."""
from pathlib import Path


def test_legacy_quarantine_is_exact_loan_and_tenant_scoped():
    source = (Path(__file__).resolve().parents[1] / "services" / "legacy_loan_quarantine.py").read_text()
    assert "LegacyLoanCapture.loan_id == loan_model.id" in source
    assert "LegacyLoanCapture.company_id == loan_model.company_id" in source
    assert "borrower_id" not in source
    assert "national_id" not in source
    assert "query.filter(~legacy_capture_exists_for_loan(loan_model))" in source
