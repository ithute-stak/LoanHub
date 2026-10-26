"""The CDAS ledger queue supports tenant-scoped paged review."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
ROUTER = ROOT / "apps/backend/routers/cdas_api.py"
PAGE = ROOT / "apps/frontend/app/(dashboard)/company/cdas/manage/page.tsx"


def test_ledger_pagination_keeps_tenant_filter_and_stable_sort():
    source = ROUTER.read_text(encoding="utf-8")
    section = source.split('@router.get("/operations")', 1)[1].split('@router.get("/operations/{operation_id}")', 1)[0]
    for expected in (
        'offset: int = Query(default=0, ge=0)',
        'CdasProviderOperation.company_id == context.company_id',
        'CdasProviderOperation.state.in_(UNRESOLVED_OPERATION_STATES)',
        'total = query.count()',
        'CdasProviderOperation.id.desc()',
        '.offset(offset).limit(limit).all()',
        '"has_more": offset + len(items) < total',
    ):
        assert expected in section


def test_management_queue_has_server_paging_controls():
    source = PAGE.read_text(encoding="utf-8")
    assert 'loadLedger(ledgerFilter, Math.max(0, ledgerOffset - 50))' in source
    assert 'loadLedger(ledgerFilter, ledgerOffset + 50)' in source
    assert 'setLedgerHasMore(response.data.has_more)' in source
    assert 'setLedgerTotal(response.data.total)' in source
    assert 'Search applies to this page.' in source
