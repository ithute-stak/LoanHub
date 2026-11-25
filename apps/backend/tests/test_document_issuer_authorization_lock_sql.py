"""Static fail-closed contracts for the draft delegated issuer authorization lock.

These do NOT substitute for PostgreSQL transaction/role integration tests.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SQL = (ROOT / "scripts" / "provision_document_issuer_authorization_lock.sql").read_text()


def test_authorization_lock_uses_unspoofable_issuer_login_binding():
    assert "SECURITY DEFINER" in SQL
    assert "SET search_path = pg_catalog" in SQL
    assert "b.login_name = session_user AND b.company_id = p_company_id" in SQL
    assert "NOT r.rolsuper AND NOT r.rolbypassrls" in SQL
    assert "loanhub.company_id" not in SQL


def test_authorization_lock_prevents_revoked_membership_and_unapproved_company():
    for fragment in (
        "u.is_active IS TRUE",
        "u.must_change_password IS FALSE",
        "c.is_active IS TRUE",
        "c.status::text = 'APPROVED'",
        "s.user_id = p_user_id",
        "s.company_id = p_company_id",
        "s.is_active IS TRUE",
        "s.role::text IN ('COMPANY_OWNER', 'COMPANY_ADMIN')",
    ):
        assert fragment in SQL
    assert SQL.count("FOR SHARE NOWAIT") == 3


def test_authorization_lock_never_grants_public_execution_or_update():
    assert "REVOKE ALL ON FUNCTION public.lock_document_issuer_authorization" in SQL
    assert "FROM PUBLIC;" in SQL
    assert "GRANT EXECUTE" not in SQL
    assert "UPDATE public." not in SQL
    assert "DELETE FROM public." not in SQL
