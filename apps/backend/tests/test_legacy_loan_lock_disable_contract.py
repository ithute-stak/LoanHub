"""Contract tests for management-only audited legacy lock emergency disable."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROUTER = (ROOT / "routers" / "loan_settings.py").read_text()
SERVICE = (ROOT / "services" / "legacy_loan_lock_transition.py").read_text()


def test_disable_endpoint_requires_company_management_and_audit_service():
    endpoint = ROUTER.split("def disable_legacy_loan_lock(", 1)[1]
    assert 'require_tenant_roles(context, COMPANY_MANAGEMENT_ROLES)' in endpoint
    assert "company_id=context.company_id" in endpoint
    assert "actor_user_id=context.user.id" in endpoint
    assert "enabled=False" in endpoint
    assert "transition_legacy_loan_lock(" in endpoint


def test_transition_is_fail_closed_for_activation_and_audits_disable():
    assert "if enabled:" in SERVICE
    assert "status_code=409" in SERVICE
    assert ".with_for_update()" in SERVICE
    assert 'action="legacy_loan_lock.disabled"' in SERVICE
    assert "db.commit()" in SERVICE


def test_no_enable_endpoint_exists():
    assert '@router.post("/legacy-loan-lock/enable"' not in ROUTER
    assert '@router.put("/legacy-loan-lock/enable"' not in ROUTER
