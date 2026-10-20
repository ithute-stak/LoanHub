"""Guard that CDAS history displays only verified scoped mandate details."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = (ROOT / "routers/cdas_api.py").read_text()
FRONTEND = (ROOT.parent / "frontend/app/(dashboard)/company/cdas/history/page.tsx").read_text()


def test_transaction_history_enrichment_scoped_and_exact():
    section = BACKEND.split('    # Enrich only with mandates', 1)[1].split('    def sort_key(', 1)[0]
    assert "CDASDeductionMandate.company_id == context.company_id" in section
    assert "CDASDeductionMandate.branch_id == context.branch_id" in section
    assert "mandate.employee_number" in section
    assert "mandate.external_reference" in section
    assert "len(matches) == 1" in section
    assert '"details_source": "not_verified"' in section
    assert 'item["details_source"] = "ambiguous_match"' in section


def test_portal_columns_use_nullable_verified_data():
    for field in ("monthly_deduction", "principal_amount", "total_installments",
                  "starting_month", "ending_month", "policy_reference", "details_source"):
        assert field in FRONTEND
    assert "No verified mandate details" in FRONTEND
