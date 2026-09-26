from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_credit_committee_new_routes_are_discoverable_from_lending_workspaces():
    lending_page = (ROOT / "frontend" / "app" / "(dashboard)" / "company" / "lending-operations" / "page.tsx").read_text(encoding="utf-8")
    loans_layout = (ROOT / "frontend" / "app" / "(dashboard)" / "company" / "loans" / "layout.tsx").read_text(encoding="utf-8")
    assert "/company/credit-committee" in lending_page
    assert "/company/credit-committee" in loans_layout


def test_committee_pdf_and_condition_date_normalization_are_present():
    report = (ROOT / "backend" / "services" / "credit_committee_report_service.py").read_text(encoding="utf-8")
    integrity = (ROOT / "backend" / "core" / "credit_committee_integrity.py").read_text(encoding="utf-8")
    assert "Credit Committee Credit Memo" in report
    assert "Committee votes" in report
    assert "Final decision and conditions" in report
    assert "date.fromisoformat" in integrity
    assert 'event.listen(CreditCommitteeCondition, "before_insert", _normalize_condition_date)' in integrity
