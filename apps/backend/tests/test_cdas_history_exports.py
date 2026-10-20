"""Regression checks for scoped and filter-consistent CDAS history exports."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API = (ROOT / "routers/cdas_api.py").read_text()
UI = (ROOT.parent / "frontend/app/(dashboard)/company/cdas/history/page.tsx").read_text()


def test_both_exports_use_same_filtered_history():
    block = API.split("def _filtered_history_export(", 1)[1].split('@router.get("/history/deductions")', 1)[0]
    assert block.count("_filtered_history_export(") == 3
    for field in ("search=search", "state=state", "operation_type=operation_type",
                  "actor_user_id=actor_user_id", "date_from=date_from",
                  "date_to=date_to", "sort_order=sort_order"):
        assert block.count(field) >= 3
    assert 'if history["total"] > limit:' in block
    assert 'get_cdas_transaction_log(' in block


def test_csv_injection_guard_and_file_downloads():
    assert 'lstrip().startswith(("=", "+", "-", "@"))' in API
    assert '"/cdas/history/transactions.csv?" + transactionExportFilters()' in UI
    assert '"/cdas/history/transactions.pdf?" + transactionExportFilters()' in UI
    assert 'params.set("date_from", dateFrom)' in UI
    assert 'params.set("date_to", dateTo)' in UI
