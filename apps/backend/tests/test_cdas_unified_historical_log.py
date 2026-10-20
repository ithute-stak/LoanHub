"""Approved historical evidence appears alongside live history without financial posting."""
from pathlib import Path
root = Path(__file__).resolve().parents[1]
api = (root / "routers/cdas_api.py").read_text()
ui = (root.parent / "frontend/app/(dashboard)/company/cdas/history/page.tsx").read_text()
log = api.split('@router.get("/history/transactions")', 1)[1].split('@router.get("/history/transactions.pdf")', 1)[0]


def test_only_scoped_approved_historical_rows_are_included():
    assert 'CdasHistoricalImportRow.company_id == context.company_id' in log
    assert 'CdasHistoricalImportRow.branch_id == context.branch_id' in log
    assert 'CdasHistoricalImportRow.reconciliation_status == "approved"' in log
    assert '"source": "historical_import"' in log
    assert '"historical_date_unverified": True' in log


def test_historical_evidence_not_labeled_as_payment():
    assert '"state": "approved_evidence"' in log
    assert '"operation_type": "historical_record"' in log
    assert "Approved imported evidence" in ui
    assert "not proof of a collected payment" in ui
