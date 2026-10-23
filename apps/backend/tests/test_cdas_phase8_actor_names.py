"""CDAS ledger displays staff names while tenant-scoping identity lookup."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
ROUTER = ROOT / "apps/backend/routers/cdas_api.py"
PAGE = ROOT / "apps/frontend/app/(dashboard)/company/cdas/manage/page.tsx"


def test_actor_name_lookup_is_company_scoped():
    source = ROUTER.read_text(encoding="utf-8")
    start = source.index("def list_cdas_operations(")
    end = source.index('@router.get("/operations/{operation_id}")', start)
    body = source[start:end]
    assert "CompanyStaff.company_id == context.company_id" in body
    assert "CompanyStaff.user_id.in_(actor_ids)" in body
    assert 'item["actor_name"]' in body


def test_frontend_displays_name_and_keeps_staff_user_id():
    source = PAGE.read_text(encoding="utf-8")
    assert "actor_name: string | null" in source
    assert 'item.actor_name || "Name unavailable"' in source
    assert 'item.actor_user_id || "Unavailable"' in source
