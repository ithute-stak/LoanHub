"""CDAS age alert must describe the age actually measured."""
from pathlib import Path

PAGE = Path(__file__).resolve().parents[3] / "apps/frontend/app/(dashboard)/company/cdas/manage/page.tsx"


def test_age_warning_is_explicit_about_creation_not_reconciliation_state_change():
    source = PAGE.read_text(encoding="utf-8")
    section = source.split('function unresolvedAgeLabel(', 1)[1].split('function money(', 1)[0]
    assert 'operation.created_at' in section
    assert '"Open operation created "' in section
    assert '"Unresolved for "' not in section
    assert 'if (hours < 24) return null;' in section
