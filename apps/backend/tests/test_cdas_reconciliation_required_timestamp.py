"""First reconciliation timestamp persists across checks and is exposed to managers."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
MODEL = ROOT / "apps/backend/database/models/cdas_official.py"
LEDGER = ROOT / "apps/backend/services/cdas_operation_ledger.py"
PAGE = ROOT / "apps/frontend/app/(dashboard)/company/cdas/manage/page.tsx"


def test_first_reconciliation_timestamp_is_preserved_across_rechecks():
    source = LEDGER.read_text(encoding="utf-8")
    assert source.count("if not operation.requires_reconciliation and operation.reconciliation_required_at is None:") == 3
    assert source.count("operation.reconciliation_required_at = _utcnow_naive()") == 3
    assert '"reconciliation_required_at": operation.reconciliation_required_at.isoformat()' in source
    assert "reconciliation_required_at = Column(DateTime, nullable=True)" in MODEL.read_text(encoding="utf-8")


def test_manager_warning_uses_reconciliation_timestamp_with_legacy_fallback():
    source = PAGE.read_text(encoding="utf-8")
    section = source.split("function unresolvedAgeLabel(", 1)[1].split("function money(", 1)[0]
    assert "operation.reconciliation_required_at || operation.created_at" in section
    assert "Reconciliation required for " in section
    assert "Open operation created " in section
    assert "Reconciliation required since" in source
