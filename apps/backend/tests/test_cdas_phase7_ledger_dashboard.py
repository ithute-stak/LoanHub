"""CDAS management ledger provides scoped searchable operation audit visibility."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PAGE = ROOT / "apps/frontend/app/(dashboard)/company/cdas/manage/page.tsx"
ROUTER = ROOT / "apps/backend/routers/cdas_api.py"


def test_cdas_management_reads_company_scoped_ledger_and_displays_staff():
    source = PAGE.read_text(encoding="utf-8")
    assert '"/cdas/operations?limit=200"' in source
    assert "actor_user_id" in source
    assert "Staff user ID:" in source
    assert "item.requires_reconciliation" in source
    assert 'setLedgerFilter("unresolved")' in source
    assert 'setLedgerFilter("all")' in source
    assert "Search CDAS operation ledger" in source


def test_cdas_ledger_api_is_company_scoped():
    source = ROUTER.read_text(encoding="utf-8")
    start = source.index('def list_cdas_operations(')
    end = source.index('@router.get("/operations/{operation_id}")', start)
    fragment = source[start:end]
    assert "_require_company_manager(context)" in fragment
    assert "CdasProviderOperation.company_id == context.company_id" in fragment
