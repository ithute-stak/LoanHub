"""CDAS management highlights unresolved operations older than one day."""
from pathlib import Path

PAGE = Path(__file__).resolve().parents[3] / "apps/frontend/app/(dashboard)/company/cdas/manage/page.tsx"


def test_long_unresolved_operations_show_review_priority_without_provider_write():
    source = PAGE.read_text(encoding="utf-8")
    assert 'function unresolvedAgeLabel(operation: CdasLedgerOperation)' in source
    assert 'if (!operation.requires_reconciliation || !operation.created_at) return null;' in source
    assert 'if (hours < 24) return null;' in source
    assert '{unresolvedAgeLabel(item) && <Badge variant="destructive">' in source
    assert 'prioritize provider verification.' in source
    assert 'Reconcile (read-only)' in source
