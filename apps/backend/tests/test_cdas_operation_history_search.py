"""CDAS operation history search runs on the tenant-scoped query before pagination."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
ROUTER = ROOT / "apps/backend/routers/cdas_api.py"
PAGE = ROOT / "apps/frontend/app/(dashboard)/company/cdas/manage/page.tsx"


def test_history_search_is_tenant_scoped_and_applied_before_paging():
    source = ROUTER.read_text(encoding="utf-8")
    section = source.split('@router.get("/operations")', 1)[1].split('@router.get("/operations/{operation_id}")', 1)[0]
    assert 'search: str | None = Query(default=None, max_length=120)' in section
    assert 'CdasProviderOperation.company_id == context.company_id' in section
    assert 'CdasProviderOperation.employee_no.ilike(' in section
    assert 'CdasProviderOperation.reference_no.ilike(' in section
    assert 'CdasProviderOperation.state.ilike(' in section
    assert 'cast(CdasProviderOperation.deduction_id, String).ilike(' in section
    assert section.index('query = query.filter(or_(') < section.index('total = query.count()') < section.index('.offset(offset).limit(limit).all()')


def test_manager_search_applies_to_full_queue_and_preserves_paging():
    source = PAGE.read_text(encoding="utf-8")
    assert 'encodeURIComponent(term.trim())' in source
    assert 'void loadLedger(ledgerFilter, 0, ledgerSearch)' in source
    assert 'term = appliedLedgerSearch' in source
    assert 'Search covers the selected queue history.' in source
