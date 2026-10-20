"""History review is a reporting-only transition, never a collection action."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API = (ROOT / "routers/cdas_api.py").read_text()
UI = (ROOT.parent / "frontend/app/(dashboard)/company/cdas/history/imports/page.tsx").read_text()
SECTION = API.split('@router.post("/history/import/batches/{batch_id}/rows/{row_id}/review")', 1)[1].split('@router.get("/history/transactions")', 1)[0]


def test_review_requires_scope_and_pending_record():
    assert "_require_company_manager(context)" in SECTION
    assert "CdasHistoricalImportBatch.company_id == context.company_id" in SECTION
    assert "CdasHistoricalImportRow.company_id == context.company_id" in SECTION
    assert "CdasHistoricalImportRow.batch_id == batch.id" in SECTION
    assert ".with_for_update().first()" in SECTION
    assert 'row.reconciliation_status != "pending"' in SECTION


def test_review_has_audit_and_never_posts_financial_operations():
    assert 'action="cdas.historical_row_reviewed"' in SECTION
    assert '"financial_postings": 0' in SECTION
    assert "db.add(CDASDeductionMandate(" not in SECTION
    assert "db.add(PaymentTransaction(" not in SECTION
    assert "execute_provider_operation(" not in SECTION
    assert 'reviewRow(row.id, "approved")' in UI
    assert 'reviewRow(row.id, "rejected")' in UI
