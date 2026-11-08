"""Independent document-bound handwriting evidence; not automatic signing."""
from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from database.base import Base


class WacomDocumentIntent(Base):
    __tablename__ = "wacom_document_intents"
    __table_args__ = (
        CheckConstraint("status IN ('prepared','consented','evidence_uploaded','verified','rejected','expired','cancelled')", name="ck_wacom_doc_intent_status"),
        CheckConstraint("length(document_sha256) = 64 AND length(binding_sha256) = 64", name="ck_wacom_doc_hashes"),
        UniqueConstraint("company_id", "contract_id", "document_sha256", "borrower_id", name="uq_wacom_doc_intent_exact_document"),
        Index("ix_wacom_doc_intent_actor", "company_id", "operator_user_id", "status"),
    )
    company_id = Column(UUID(as_uuid=True), ForeignKey("loan_companies.id", ondelete="RESTRICT"), nullable=False)
    borrower_id = Column(UUID(as_uuid=True), ForeignKey("borrowers.id", ondelete="RESTRICT"), nullable=False)
    contract_id = Column(UUID(as_uuid=True), ForeignKey("loan_contracts.id", ondelete="RESTRICT"), nullable=False)
    source_file_id = Column(UUID(as_uuid=True), ForeignKey("managed_files.id", ondelete="RESTRICT"), nullable=False)
    operator_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    workstation_id = Column(UUID(as_uuid=True), nullable=False)
    document_sha256 = Column(String(64), nullable=False)
    document_version = Column(String(80), nullable=False)
    binding_sha256 = Column(String(64), nullable=False)
    status = Column(String(24), default="prepared", nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    consent_reference = Column(String(180))
    consent_commitment_sha256 = Column(String(64))
    consent_at = Column(DateTime(timezone=True))
    evidence_file_id = Column(UUID(as_uuid=True), ForeignKey("managed_files.id", ondelete="RESTRICT"))
    evidence_sha256 = Column(String(64))
    review_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"))
    review_at = Column(DateTime(timezone=True))
    review_reference = Column(String(180))
    review_reason = Column(Text)
