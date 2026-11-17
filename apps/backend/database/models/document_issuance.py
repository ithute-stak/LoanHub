"""Tenant-owned immutable document issuance identity and current status.

Never store PDF contents in this table. The final PDF must be retained in a
separately access-controlled immutable object store. Its SHA-256 here is over
the exact final stored bytes for the issued version, including any signatures.
A subsequently signed file is a distinct issuance/version with its own digest.
"""
from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, Index, func
from sqlalchemy.dialects.postgresql import UUID

from database.base import Base


class DocumentIssuance(Base):
    __tablename__ = "document_issuances"
    __table_args__ = (
        UniqueConstraint("public_id", name="uq_document_issuances_public_id"),
        UniqueConstraint("company_id", "idempotency_key", name="uq_document_issuances_tenant_idempotency"),
        Index("ix_document_issuances_tenant_source", "company_id", "source_type", "source_id"),
        CheckConstraint("version >= 1", name="ck_document_issuances_version_positive"),
        CheckConstraint(
            "status IN ('issued', 'revoked', 'superseded')",
            name="ck_document_issuances_known_status",
        ),
    )

    company_id = Column(UUID(as_uuid=True), ForeignKey("loan_companies.id", ondelete="RESTRICT"), nullable=False, index=True)
    public_id = Column(String(96), nullable=False)
    idempotency_key = Column(String(120), nullable=False)
    source_type = Column(String(80), nullable=False)
    source_id = Column(String(120), nullable=False)
    document_type = Column(String(80), nullable=False)
    version = Column(Integer, nullable=False, default=1)
    stamp_configuration_version = Column(Integer, nullable=False, default=1)
    final_pdf_sha256 = Column(String(64), nullable=False)
    # Object ID (not a public URL) referencing an immutable, private PDF.
    artifact_key = Column(String(255), nullable=False)
    status = Column(String(16), nullable=False, default="issued")
    issued_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    issued_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    supersedes_id = Column(UUID(as_uuid=True), ForeignKey("document_issuances.id", ondelete="RESTRICT"), nullable=True)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    revoked_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True)
    revocation_reason = Column(Text, nullable=True)


class DocumentIssuanceEvent(Base):
    """Append-only events: INSERT privilege only for application role.

    Database privileges/triggers and immutable backups must enforce this;
    a Python model alone cannot guarantee append-only behavior.
    """
    __tablename__ = "document_issuance_events"
    __table_args__ = (
        Index("ix_document_issuance_events_issuance_time", "issuance_id", "created_at"),
    )
    company_id = Column(UUID(as_uuid=True), ForeignKey("loan_companies.id", ondelete="RESTRICT"), nullable=False, index=True)
    issuance_id = Column(UUID(as_uuid=True), ForeignKey("document_issuances.id", ondelete="RESTRICT"), nullable=False)
    event_type = Column(String(40), nullable=False)
    actor_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    detail = Column(Text, nullable=True)
