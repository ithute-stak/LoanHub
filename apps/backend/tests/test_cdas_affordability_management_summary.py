"""Phase 5 management summary safety tests."""
from datetime import datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest

from routers.cdas_government_employees import stored_assessment_summary
from services.cdas_affordability_summary_pdf import build_government_affordability_summary_pdf


def record(*, mismatched=False):
    borrower_id = uuid4()
    return SimpleNamespace(
        id=uuid4(),
        record_id=borrower_id,
        event_data={"snapshot": {
            "borrower_id": str(uuid4()) if mismatched else str(borrower_id),
            "reference": "CDAS-AFF-TEST",
            "employee_number": "EMP-100",
            "assessed_at": "2026-11-18T15:00:00Z",
            "cdas_capacity": "100.00",
            "maximum_affordable_installment": "80.00",
            "proposed_installment": "50.00",
            "decision": "pass",
            "policy_version": 3,
            "assessment": {"monthly_income": "confidential"},
        }},
    )


def test_summary_exposes_only_allowed_fields():
    item = stored_assessment_summary(record())
    assert item["reference"] == "CDAS-AFF-TEST"
    assert "assessment" not in item
    assert "monthly_income" not in item


def test_summary_rejects_conflicting_archived_borrower():
    with pytest.raises(ValueError):
        stored_assessment_summary(record(mismatched=True))


def test_consolidated_pdf_uses_saved_rows(monkeypatch):
    import services.cdas_affordability_summary_pdf as m
    monkeypatch.setattr(m, "draw_brand_header", lambda *args, **kwargs: None)
    monkeypatch.setattr(m, "draw_brand_footer", lambda *args, **kwargs: None)
    pdf = build_government_affordability_summary_pdf(
        db=None, company=None,
        rows=[stored_assessment_summary(record())],
        generated_at="2026-11-18T15:00:00Z",
    )
    assert pdf.startswith(b"%PDF-")
    assert len(pdf) > 1000


def test_empty_consolidated_report_is_valid(monkeypatch):
    import services.cdas_affordability_summary_pdf as m
    monkeypatch.setattr(m, "draw_brand_header", lambda *args, **kwargs: None)
    monkeypatch.setattr(m, "draw_brand_footer", lambda *args, **kwargs: None)
    result = build_government_affordability_summary_pdf(
        db=None, company=None, rows=[], generated_at="2026-11-18",
    )
    assert result.startswith(b"%PDF-")


@pytest.mark.parametrize("field,value", [
    ("reference", None), ("reference", "   "),
    ("assessed_at", None), ("assessed_at", ""),
    ("decision", None), ("decision", " "),
])
def test_summary_rejects_missing_essential_result_metadata(field, value):
    archived = record()
    archived.event_data["snapshot"][field] = value
    with pytest.raises(ValueError, match="required result metadata"):
        stored_assessment_summary(archived)
