from sqlalchemy import CheckConstraint, UniqueConstraint

from database.base import Base
from database.models.document_issuance import DocumentIssuance, DocumentIssuanceEvent


def test_issuance_records_are_tenant_scoped_and_idempotent():
    table = DocumentIssuance.__table__
    assert {"company_id", "public_id", "idempotency_key", "final_pdf_sha256",
            "artifact_key", "source_pdf_sha256", "issued_by_user_id", "stamp_configuration_version",
            "status", "revocation_reason"}.issubset(table.c.keys())
    assert table.c.company_id.nullable is False
    assert table.c.source_pdf_sha256.nullable is False
    assert table.c.final_pdf_sha256.nullable is False
    assert table.c.artifact_key.nullable is False
    assert table.c.issued_by_user_id.nullable is False
    assert any(
        isinstance(item, UniqueConstraint)
        and {column.name for column in item.columns} == {"company_id", "idempotency_key"}
        for item in table.constraints
    )
    assert any(
        isinstance(item, UniqueConstraint)
        and {column.name for column in item.columns} ==
        {"company_id", "source_type", "source_id", "document_type", "version"}
        for item in table.constraints
    )
    assert any(isinstance(item, CheckConstraint) and "status" in str(item.sqltext)
               for item in table.constraints)


def test_audit_events_retain_tenant_and_issuance_binding():
    table = DocumentIssuanceEvent.__table__
    assert table.c.company_id.nullable is False
    assert table.c.issuance_id.nullable is False
    assert table.c.actor_user_id.nullable is False
    assert "document_issuances" in Base.metadata.tables
    assert "document_issuance_events" in Base.metadata.tables
