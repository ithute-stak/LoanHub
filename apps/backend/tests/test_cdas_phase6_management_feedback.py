"""CDAS management must distinguish reconciliation confirmation from unresolved read-back."""
from pathlib import Path

PAGE = Path(__file__).resolve().parents[2] / "frontend/app/(dashboard)/company/cdas/manage/page.tsx"


def test_cdas_reconciliation_feedback_is_based_on_provider_confirmation():
    source = PAGE.read_text(encoding="utf-8")
    assert "response.data.reconciled" in source
    assert "CDAS provider reconciliation confirmed" in source
    assert "CDAS has not confirmed this deduction yet" in source
    assert "{reconciliationFeedback}" in source
