"""CDAS operation review uses existing scoped read-only reconciliation endpoints."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PAGE = ROOT / "apps/frontend/app/(dashboard)/company/cdas/manage/page.tsx"
ROUTER = ROOT / "apps/backend/routers/cdas_api.py"


def test_manager_review_and_reconciliation_actions():
    source = PAGE.read_text(encoding="utf-8")
    assert 'api.get<CdasLedgerOperation>("/cdas/operations/" + encodeURIComponent(operationId))' in source
    assert '"/cdas/operations/" + encodeURIComponent(operationId) + "/reconcile"' in source
    assert 'Reconcile (read-only)' in source
    assert 'reviewedOperation.requires_reconciliation' in source
    assert 'setReviewedOperation(response.data.operation)' in source
    assert 'await loadLedger(ledgerFilter, ledgerOffset)' in source


def test_backend_reconciliation_retains_tenant_and_environment_checks():
    source = ROUTER.read_text(encoding="utf-8")
    section = source.split('@router.post("/operations/{operation_id}/reconcile")', 1)[1].split('@router.post("/employees/verify")', 1)[0]
    assert '_require_company_manager(context)' in section
    assert 'CdasProviderOperation.company_id == context.company_id' in section
    assert 'operation.environment != current_environment' in section
    assert 'reconcile_provider_operation(db, operation=operation, client=client)' in section
