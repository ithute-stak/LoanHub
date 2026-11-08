"""Review that approval routes remain gated and cannot execute contracts."""
from routers import wacom_finalization_approvals as routes


def test_approval_route_off_by_default(monkeypatch):
    from fastapi import HTTPException
    monkeypatch.delenv("LOANHUB_WACOM_FINAL_APPROVALS_ENABLED", raising=False)
    try:
        routes._gate()
        assert False, "Approval feature enabled by default"
    except HTTPException as exc:
        assert exc.status_code == 503


def test_approval_router_has_exactly_request_and_decision_operations():
    operations = {(method, route.path) for route in routes.router.routes
                  for method in (route.methods or set())}
    assert operations == {
        ("POST", "/wacom-finalization-approvals/intents/{intent_id}"),
        ("POST", "/wacom-finalization-approvals/{approval_id}/decision"),
    }


def test_no_contract_mutation_or_pdf_signing_in_approval_handler():
    import inspect
    code = inspect.getsource(routes)
    for unsafe in ("borrower_signed_at =", "company_signed_at =", "refresh_contract_pdf_after_signature(",
                   "store_bytes(", "sign_pdf(", "disburse("):
        assert unsafe not in code
