"""CDAS management queue uses server-side unresolved ledger filtering."""
from pathlib import Path

PAGE = Path(__file__).resolve().parents[3] / "apps/frontend/app/(dashboard)/company/cdas/manage/page.tsx"


def test_manager_queue_loads_server_filtered_unresolved_operations():
    source = PAGE.read_text(encoding="utf-8")
    assert 'api.get<CdasLedgerResponse>("/cdas/operations?limit=200&unresolved_only=true")' in source
    assert 'async function loadLedger(mode: "all" | "unresolved")' in source
    assert 'setLedgerItems(response.data.items)' in source
    assert 'setLedgerFilter(mode)' in source
    assert 'void loadLedger("unresolved")' in source
    assert 'void loadLedger("all")' in source
    assert 'if (ledgerFilter === "unresolved" && !item.requires_reconciliation) return false;' not in source
