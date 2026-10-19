"""Smoke tests for LoanHub's server-rendered live CDAS history PDF."""
from datetime import datetime, timezone
from types import SimpleNamespace

from services import cdas_history_pdf


def test_cdas_history_pdf_is_rendered_on_backend_with_repeated_branding(monkeypatch):
    calls = {"headers": 0, "footers": 0}

    def header(canvas, **kwargs):
        calls["headers"] += 1
        assert kwargs["company"].name == "Example Lender"
        assert kwargs["title"] == "CDAS OPERATIONS HISTORY"

    def footer(canvas, doc, **kwargs):
        calls["footers"] += 1

    monkeypatch.setattr(cdas_history_pdf, "draw_brand_header", header)
    monkeypatch.setattr(cdas_history_pdf, "draw_brand_footer", footer)
    entries = [
        {
            "occurred_at": datetime(2026, 10, 19, 8, 30, tzinfo=timezone.utc),
            "source": "provider_operation",
            "operation_type": "modify",
            "state": "completed",
            "employee_no": "0001234",
            "reference_no": f"REF-{i:04d}",
            "provider_status_code": "200",
        }
        for i in range(100)
    ]
    payload = cdas_history_pdf.build_cdas_history_pdf(
        db=None, company=SimpleNamespace(name="Example Lender"),
        entries=entries, environment="production"
    )
    assert payload.startswith(b"%PDF-")
    assert len(payload) > 1000
    assert calls["headers"] > 1
    assert calls["headers"] == calls["footers"]


def test_cdas_history_pdf_handles_empty_ledger(monkeypatch):
    monkeypatch.setattr(cdas_history_pdf, "draw_brand_header", lambda *a, **k: None)
    monkeypatch.setattr(cdas_history_pdf, "draw_brand_footer", lambda *a, **k: None)
    payload = cdas_history_pdf.build_cdas_history_pdf(
        db=None, company=SimpleNamespace(name="Example Lender"),
        entries=[], environment="production"
    )
    assert payload.startswith(b"%PDF-")
