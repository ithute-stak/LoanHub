"""Guard the document issuance migration against destructive drift."""
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

from sqlalchemy import CheckConstraint, UniqueConstraint

from database.models.document_issuance import DocumentIssuance, DocumentIssuanceEvent


def test_document_issuance_migration_matches_registered_model_columns():
    path = (
        Path(__file__).resolve().parents[1]
        / "alembic/versions/c5d6e7f8a912_document_issuance_registry.py"
    )
    spec = spec_from_file_location("document_issuance_migration", path)
    module = module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    assert module.revision == "c5d6e7f8a912"
    assert module.down_revision == "b4c5d6e7f801"

    required_issuance = {
        "company_id", "public_id", "idempotency_key", "source_type",
        "source_id", "document_type", "version",
        "stamp_configuration_version", "source_pdf_sha256",
        "final_pdf_sha256", "artifact_key", "status", "issued_at",
        "issued_by_user_id", "supersedes_id", "revoked_at",
        "revoked_by_user_id", "revocation_reason",
    }
    assert required_issuance.issubset(DocumentIssuance.__table__.c.keys())
    assert {column.name for column in DocumentIssuanceEvent.__table__.columns} >= {
        "company_id", "issuance_id", "event_type", "actor_user_id", "detail"
    }
    constraints = DocumentIssuance.__table__.constraints
    names = {c.name for c in constraints if isinstance(c, UniqueConstraint)}
    assert {
        "uq_document_issuances_public_id",
        "uq_document_issuances_tenant_idempotency",
        "uq_document_issuances_source_version",
    } <= names
    assert any(isinstance(c, CheckConstraint) and c.name == "ck_document_issuances_known_status"
               for c in constraints)


def test_tenant_rls_policies_fail_closed_and_bind_audit_event():
    source = (
        Path(__file__).resolve().parents[1]
        / "alembic/versions/c5d6e7f8a912_document_issuance_registry.py"
    ).read_text(encoding="utf-8")
    assert "ENABLE ROW LEVEL SECURITY" in source
    assert 'FOR SELECT USING ({tenant_predicate})' in source
    assert 'FOR INSERT WITH CHECK ({issuer_predicate}' in source
    assert "loanhub.actor_scope" in source
    assert "loanhub.company_id" in source
    assert "loanhub.user_id" in source
    assert "company_owner" in source and "company_admin" in source
    assert "i.id = document_issuance_events.issuance_id" in source
    assert "FOR UPDATE" not in source and "FOR DELETE" not in source
    assert "BYPASSRLS" in source
