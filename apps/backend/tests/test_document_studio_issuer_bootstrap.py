"""Fail-closed contracts for the dedicated official document issuer bootstrap."""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
ISSUER = (ROOT / "scripts" / "bootstrap_document_issuer_role.sh").read_text()
RUNTIME = (ROOT / "scripts" / "ensure_database_runtime_role.sh").read_text()


def test_issuer_bootstrap_requires_out_of_band_secret_and_uses_separate_login():
    assert '${ISSUER_DB_PASSWORD:?ISSUER_DB_PASSWORD required}' in ISSUER
    assert 'ISSUER_DB_USER:=loanhub_document_issuer' in ISSUER
    assert 'Issuer login must differ from schema owner' in ISSUER
    for control in ('NOSUPERUSER', 'NOBYPASSRLS', 'NOCREATEDB', 'NOCREATEROLE', 'NOREPLICATION'):
        assert control in ISSUER
    assert 'REVOKE ALL ON ALL TABLES IN SCHEMA public' in ISSUER


def test_issuer_cannot_write_approval_history_or_change_existing_issuance():
    assert 'GRANT SELECT ON TABLE document_stamp_approvals, document_stamp_approval_revocations' in ISSUER
    assert 'GRANT SELECT, INSERT ON TABLE document_issuances, document_issuance_events' in ISSUER
    assert 'GRANT SELECT ON TABLE users, loan_companies, company_staff, workspace_documents' in ISSUER
    assert 'GRANT SELECT, UPDATE ON TABLE users, loan_companies, company_staff, workspace_documents' not in ISSUER
    # Source locking is delegated to a tenant-bound SECURITY DEFINER function;
    # even an authorized issuer must not edit source rows directly.
    assert "GRANT UPDATE ON TABLE" not in ISSUER
    assert 'GRANT SELECT ON TABLE workspace_document_signatures' in ISSUER
    assert 'GRANT DELETE ON TABLE' not in ISSUER


def test_normal_runtime_provisioner_revokes_issuance_and_approval_writes():
    assert 'REVOKE INSERT, UPDATE, DELETE ON TABLE' in RUNTIME
    for table in (
        'document_stamp_approvals', 'document_stamp_approval_revocations',
        'document_issuances', 'document_issuance_events',
    ):
        assert table in RUNTIME


def test_issuer_bootstrap_fails_closed_without_tenant_rls_on_all_source_tables():
    assert "Issuer bootstrap refused: missing tenant RLS" in ISSUER
    assert "c.relrowsecurity IS NOT TRUE" in ISSUER
    for table in ("users", "loan_companies", "company_staff", "workspace_documents"):
        assert f"'{table}'" in ISSUER


def test_runtime_issuer_restrictions_do_not_remove_existing_data_center_guards():
    assert "data_center_runtime_permission_guard" in RUNTIME
    assert "loanhub_dc_pilot_audit" in RUNTIME
    assert "REVOKE ALL ON TABLE public.%I" in RUNTIME
