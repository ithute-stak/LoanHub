"""Changing CDAS ledger context must not leave an unrelated operation open."""
from pathlib import Path

PAGE = Path(__file__).resolve().parents[3] / "apps/frontend/app/(dashboard)/company/cdas/manage/page.tsx"


def test_queue_navigation_clears_stale_review_but_reconciliation_retains_feedback():
    source = PAGE.read_text(encoding="utf-8")
    load = source.split('  async function loadLedger(', 1)[1].split('  async function reviewOperation(', 1)[0]
    assert 'keepReview = false' in load
    assert 'if (!keepReview) setReviewedOperation(null)' in load
    assert 'setLedgerItems(response.data.items)' in load
    assert 'await loadLedger(ledgerFilter, ledgerOffset, appliedLedgerSearch, true)' in source
    assert 'setReviewedOperation(response.data.operation)' in source
