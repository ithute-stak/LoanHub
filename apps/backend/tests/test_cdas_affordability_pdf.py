"""Standalone document-renderer contract tests (CDAS is never contacted)."""
import pytest
from services.cdas_affordability_pdf import build_government_affordability_pdf


def test_incomplete_stored_snapshot_is_rejected():
    with pytest.raises(ValueError, match="Incomplete stored affordability assessment"):
        build_government_affordability_pdf(db=None, company=None, snapshot={})


def test_report_uses_stored_values_and_no_provider(monkeypatch):
    from services import cdas_affordability_pdf as module
    # Branding is a presentation detail; the contract is that stored data renders.
    monkeypatch.setattr(module, "draw_brand_header", lambda *args, **kwargs: None)
    monkeypatch.setattr(module, "draw_brand_footer", lambda *args, **kwargs: None)
    data = {
        "reference": "CDAS-AFF-TEST-001",
        "employee_number": "EMP-100",
        "borrower_id": "borrower-test",
        "assessed_at": "2026-11-18T14:00:00+00:00",
        "cdas_capacity": "1200.00",
        "proposed_installment": "650.00",
        "maximum_affordable_installment": "950.00",
        "decision": "pass",
        "policy_version": 1,
    }
    pdf = build_government_affordability_pdf(db=None, company=None, snapshot=data)
    assert pdf.startswith(b"%PDF-")
    assert len(pdf) > 1000


def test_unsafe_report_content_is_escaped(monkeypatch):
    from services import cdas_affordability_pdf as module
    monkeypatch.setattr(module, "draw_brand_header", lambda *args, **kwargs: None)
    monkeypatch.setattr(module, "draw_brand_footer", lambda *args, **kwargs: None)
    data = {
        "reference": "AFF-TEST", "employee_number": "<script>bad</script>",
        "borrower_id": "borrower", "assessed_at": "2026-11-18",
        "cdas_capacity": "100.00", "proposed_installment": "50.00",
        "maximum_affordable_installment": "70.00", "decision": "fail",
        "policy_version": 1,
    }
    pdf = build_government_affordability_pdf(db=None, company=None, snapshot=data)
    assert pdf.startswith(b"%PDF-")
