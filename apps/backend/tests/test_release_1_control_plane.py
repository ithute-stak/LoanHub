from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from core.audit_integrity import GENESIS_HASH, audit_hash, verify_chain
from database.models.audit_log import AuditLog
from services.mfa_service import totp_at, verify_totp


BACKEND = Path(__file__).resolve().parents[1]
FRONTEND = BACKEND.parent / "frontend"


def test_totp_matches_rfc_vector_and_rejects_replay():
    # RFC 6238 SHA-1 test secret, reduced to LoanHub's six displayed digits.
    secret = "GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ"
    assert totp_at(secret, 1) == "287082"
    assert verify_totp(secret, "287082", timestamp=59) == 1
    assert verify_totp(secret, "287082", timestamp=59, last_counter=1) is None


def test_audit_hash_chain_detects_tampering():
    first = AuditLog(id=uuid4(), action="loan.approved", severity="high", status="success")
    first.previous_hash = GENESIS_HASH
    first.event_hash = audit_hash(first, GENESIS_HASH)
    second = AuditLog(id=uuid4(), action="payment.posted", severity="info", status="success")
    second.previous_hash = first.event_hash
    second.event_hash = audit_hash(second, first.event_hash)
    assert verify_chain([first, second]) == (True, None)
    second.action = "payment.deleted"
    valid, broken_id = verify_chain([first, second])
    assert valid is False
    assert broken_id == str(second.id)


def test_release_migration_is_single_head_and_covers_control_domains():
    migration = (BACKEND / "alembic" / "versions" / "i9y3a5b7d809_release_1_control_plane.py").read_text()
    assert 'down_revision = "h8x2z4a6c798"' in migration
    for table in (
        "user_mfa_enrollments",
        "user_security_states",
        "payment_adjustments",
        "webhook_outbox_events",
        "accounting_periods",
        "bank_statement_lines",
        "loan_guarantors",
        "loan_collateral",
        "complaint_cases",
        "data_rights_requests",
    ):
        assert f'"{table}"' in migration


def test_login_enforces_lockout_mfa_and_session_versioning():
    auth = (BACKEND / "routers" / "auth.py").read_text()
    security = (BACKEND / "core" / "security.py").read_text()
    assert "ensure_not_locked" in auth
    assert "register_login_failure" in auth
    assert "verify_second_factor" in auth
    assert '@router.post("/mfa/enroll"' in auth
    assert '@router.get("/sessions"' in auth
    assert '"session_jti"' in security
    assert "DUMMY_PASSWORD_HASH" in security


def test_payment_adjustments_require_maker_checker_and_no_manual_gateway_completion():
    controls = (BACKEND / "services" / "governance_control_service.py").read_text()
    router = (BACKEND / "routers" / "governance_controls.py").read_text()
    assert "the requester cannot approve their own action" in controls
    assert "requires a full-payment refund or reversal" in controls
    assert "External movement must be confirmed by LelefaPayGate" in controls
    assert "confirm-gateway" not in router


def test_webhook_outbox_signs_retries_and_blocks_private_targets():
    source = (BACKEND / "services" / "webhook_outbox_service.py").read_text()
    assert "X-LoanHub-Signature" in source
    assert "follow_redirects=False" in source
    assert "dead_letter" in source
    assert "is_private" in source
    assert "with_for_update(skip_locked=True)" in source


def test_company_and_borrower_control_interfaces_are_registered():
    api_router = (BACKEND / "api" / "v1" / "router.py").read_text()
    portal = (FRONTEND / "components" / "portal" / "portal-shell.tsx").read_text()
    company_page = (FRONTEND / "app" / "(dashboard)" / "company" / "control-centre" / "page.tsx").read_text()
    borrower_page = (FRONTEND / "app" / "(dashboard)" / "borrower" / "complaints" / "page.tsx").read_text()
    assert "governance_controls.router" in api_router
    assert 'href: "/company/control-centre"' in portal
    assert 'href: "/borrower/complaints"' in portal
    assert "Control & assurance centre" in company_page
    assert "Complaints & privacy" in borrower_page
