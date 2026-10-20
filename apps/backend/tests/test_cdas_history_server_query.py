"""Regression checks for server-side CDAS transaction-history query parameters."""
from pathlib import Path

SOURCE = (Path(__file__).resolve().parents[1] / "routers/cdas_api.py").read_text()
ROUTE = SOURCE.split('@router.get("/history/transactions")', 1)[1].split('@router.get("/history/transactions.pdf")', 1)[0]


def test_filter_parameters_and_total_count():
    for field in ("page:", "search:", "state:", "operation_type:",
                  "actor_user_id:", "date_from:", "date_to:", "sort_order:"):
        assert field in ROUTE
    assert '"total": total' in ROUTE
    assert '"page": page' in ROUTE
    assert '"page_size": limit' in ROUTE


def test_scope_retained():
    assert "CdasProviderOperation.company_id == context.company_id" in ROUTE
    assert "CdasProviderOperation.branch_id == context.branch_id" in ROUTE
    assert "PlatformCdasTransaction.company_id == context.company_id" in ROUTE
    assert "if context.branch_id is None:" in ROUTE


def test_existing_export_remains_compatible():
    assert "limit: int = Query(100, ge=1, le=500)" in ROUTE
    assert 'get_cdas_transaction_log(limit=limit, context=context, db=db)' in SOURCE
