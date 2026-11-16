"""Contract checks for the non-mutating legacy loan lock status API."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROUTER = (ROOT / "routers" / "loan_settings.py").read_text()


def test_status_endpoint_is_management_only_and_company_scoped():
    endpoint = ROUTER.split('def get_legacy_loan_lock_status(', 1)[1]
    assert 'require_tenant_roles(context, COMPANY_MANAGEMENT_ROLES)' in endpoint
    assert 'LegacyLoanCapture.company_id == context.company_id' in endpoint
    assert 'legacy_loan_lock_enabled(db, context.company_id)' in endpoint


def test_status_endpoint_never_exposes_activation():
    endpoint = ROUTER.split('def get_legacy_loan_lock_status(', 1)[1]
    assert '"activation_available": False' in endpoint
    assert '@router.get("/legacy-loan-lock"' in ROUTER
    assert '@router.put("/legacy-loan-lock"' not in ROUTER
    assert '@router.post("/legacy-loan-lock"' not in ROUTER
    assert '@router.patch("/legacy-loan-lock"' not in ROUTER
