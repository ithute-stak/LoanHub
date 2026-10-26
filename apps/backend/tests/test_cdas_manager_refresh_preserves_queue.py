"""CDAS management refresh preserves operator queue context."""
from pathlib import Path

PAGE = Path(__file__).resolve().parents[3] / "apps/frontend/app/(dashboard)/company/cdas/manage/page.tsx"


def test_full_refresh_keeps_ledger_search_filter_and_page():
    source = PAGE.read_text(encoding="utf-8")
    load = source.split("  async function load() {", 1)[1].split("  async function loadLedger(", 1)[0]
    assert '"/cdas/operations?limit=50&offset=" + ledgerOffset' in load
    assert 'ledgerFilter === "unresolved"' in load
    assert 'encodeURIComponent(appliedLedgerSearch)' in load
    assert 'setLedgerOffset(ledgerResponse.data.offset)' in load
    assert 'setLedgerTotal(ledgerResponse.data.total)' in load
    assert 'setLedgerHasMore(ledgerResponse.data.has_more)' in load
