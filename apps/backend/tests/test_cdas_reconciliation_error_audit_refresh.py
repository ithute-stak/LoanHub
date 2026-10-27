"""CDAS reconciliation read errors must not leave stale operation audit details."""
from pathlib import Path

PAGE = Path(__file__).resolve().parents[3] / "apps/frontend/app/(dashboard)/company/cdas/manage/page.tsx"


def test_reconciliation_failure_refreshes_local_ledger_and_preserves_error():
    source = PAGE.read_text(encoding="utf-8")
    section = source.split('  async function reconcileLedgerOperation(', 1)[1].split('  useEffect(() => {', 1)[0]
    assert 'setError(getErrorMessage(requestError, "Read-only CDAS reconciliation could not be completed."))' in section
    assert 'const latest = await api.get<CdasLedgerOperation>("/cdas/operations/" + encodeURIComponent(operationId))' in section
    assert 'setReviewedOperation(latest.data)' in section
    assert 'await loadLedger(ledgerFilter, ledgerOffset, appliedLedgerSearch, true)' in section
    assert 'catch {' in section
    assert section.count('api.post<') == 1
