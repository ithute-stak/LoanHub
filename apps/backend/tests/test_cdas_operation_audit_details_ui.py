"""CDAS operation review displays existing audited metadata without raw payloads."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PAGE = ROOT / "apps/frontend/app/(dashboard)/company/cdas/manage/page.tsx"


def test_operation_review_includes_audit_timestamps_and_status():
    source = PAGE.read_text(encoding="utf-8")
    review = source.split('aria-label="Selected CDAS operation details"', 1)[1].split('Reconciliation checks provider records only.', 1)[0]
    for field in ('environment', 'provider_status_code', 'submitted_at', 'completed_at', 'reconciled_at', 'updated_at'):
        assert 'reviewedOperation.' + field in review
    assert 'reviewedOperation.request_snapshot' not in review
    assert 'reviewedOperation.response_snapshot' not in review
