"""CDAS operations queue exposes all unresolved states without cross-tenant leakage."""
from pathlib import Path

from services.cdas_operation_ledger import UNRESOLVED_OPERATION_STATES


ROUTER = Path(__file__).resolve().parents[1] / "routers" / "cdas_api.py"


def test_unresolved_operations_filter_uses_ledger_state_contract():
    source = ROUTER.read_text(encoding="utf-8")
    section = source.split('@router.get("/operations")', 1)[1].split('@router.get("/operations/{operation_id}")', 1)[0]
    assert "unresolved_only: bool = Query(default=False)" in section
    assert "CdasProviderOperation.state.in_(UNRESOLVED_OPERATION_STATES)" in section
    assert "CdasProviderOperation.company_id == context.company_id" in section
    assert "_require_company_manager(context)" in section
    assert "limit: int = Query(default=50, ge=1, le=200)" in section
    assert {"prepared", "submitting", "acknowledged", "unknown_provider_state", "requires_reconciliation"} <= UNRESOLVED_OPERATION_STATES
