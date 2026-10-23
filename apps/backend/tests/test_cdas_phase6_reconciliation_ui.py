"""CDAS operations UI must stop linked financial changes while reconciliation is unresolved."""
from pathlib import Path

PAGE = Path(__file__).resolve().parents[2] / "frontend/app/(dashboard)/company/cdas/operations/page.tsx"


def test_linked_reconciliation_warning_and_guard_are_present():
    source = PAGE.read_text(encoding="utf-8")
    assert "linkedState?.requires_reconciliation" in source
    assert "CDAS reconciliation required" in source
    assert "Review CDAS management" in source
    for name in ("submitLifecycle", "submitModify", "submitSettlement"):
        start = source.index(f"async function {name}(")
        end = source.index("\n    async function ", start + 1) if "\n    async function " in source[start + 1:] else source.index("\n    const affordability =", start)
        body = source[start:end]
        assert "if (linkedOperationBlocked)" in body
