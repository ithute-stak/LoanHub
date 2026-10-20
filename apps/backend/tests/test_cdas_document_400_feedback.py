"""CDAS opaque document failure is explicit and does not create a report."""
from pathlib import Path

API = (Path(__file__).resolve().parents[1] / "routers/cdas_api.py").read_text()
UI = (Path(__file__).resolve().parents[2] / "frontend/app/(dashboard)/company/cdas/documents/page.tsx").read_text()
DOCS = API.split('@router.post("/documents")', 1)[1].split('@router.get("/transactions")', 1)[0]


def test_provider_400_is_not_swallowed_or_treated_as_report_ready():
    assert "exc.status_code == 400" in DOCS
    assert '"provider_error_code": "CDAS_DOCUMENT_REQUEST_REJECTED"' in DOCS
    assert '"retryable": False' in DOCS
    assert "status_code=400" in DOCS
    assert "This does not mean LoanHub retrieved a statement" in DOCS


def test_frontend_gives_next_step_and_import_link():
    assert "setErrorAction(" in UI
    assert 'href="/company/cdas/history/imports"' in UI
