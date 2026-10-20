"""Cross-phase safety and contract checks for stacked CDAS history work.

These checks do not claim successful provider integration or historical imports.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API = (ROOT / "routers/cdas_api.py").read_text()
IMPORT = (ROOT / "services/cdas_historical_import.py").read_text()
UI = (ROOT.parent / "frontend/app/(dashboard)/company/cdas/history/page.tsx").read_text()


def test_preview_stays_separate_from_live_history():
    preview = API.split('@router.post("/history/import/preview")', 1)[1].split('@router.get("/history/transactions")', 1)[0]
    assert "_require_company_manager(context)" in preview
    assert "preview_cdas_history_csv(raw)" in preview
    assert "reconcile_preview_rows(preview[\"rows\"], candidates)" in preview
    assert 'action="cdas.historical_import_previewed"' in preview
    assert "db.add(CDASDeductionMandate(" not in preview
    assert "db.add(ClientCompanyLoan(" not in preview
    assert '"persisted": False' in IMPORT


def test_history_export_and_screen_share_filters():
    for field in ("search", "state", "operation_type", "actor_user_id", "date_from", "date_to"):
        assert f'{field}: ' in API
    assert '"/cdas/history/transactions.pdf?" + transactionExportFilters()' in UI
    assert '"/cdas/history/transactions.csv?" + transactionExportFilters()' in UI
    assert 'if history["total"] > limit:' in API


def test_history_enrichment_requires_uniquely_linked_mandate():
    section = API.split("    # Enrich only with mandates", 1)[1].split("    def sort_key(", 1)[0]
    assert "CDASDeductionMandate.company_id == context.company_id" in section
    assert "CDASDeductionMandate.branch_id == context.branch_id" in section
    assert "len(matches) == 1" in section
    assert 'item["details_source"] = "ambiguous_match"' in section
