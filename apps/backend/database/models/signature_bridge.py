"""Staging-only incoming signature vault: quarantine records, never grant signing."""
from sqlalchemy import Column, DateTime, ForeignKey, Index, LargeBinary, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from database.base import Base

class SignatureBridgeImport(Base):
    __tablename__ = "signature_bridge_imports"
    __table_args__ = (
        UniqueConstraint("company_id", "source_record_id", name="uq_signature_bridge_company_source"),
        Index("ix_signature_bridge_company_signer", "company_id", "signer_id"),
    )
    company_id = Column(UUID(as_uuid=True), ForeignKey("loan_companies.id", ondelete="RESTRICT"), nullable=False)
    source_record_id = Column(UUID(as_uuid=True), nullable=False)
    signer_kind = Column(String(12), nullable=False)
    signer_id = Column(UUID(as_uuid=True), nullable=False)
    uploaded_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    payload_ciphertext = Column(LargeBinary, nullable=False)
    payload_sha256 = Column(String(64), nullable=False)
    consent_reference = Column(String(180), nullable=False)
    phone_aliases_digest = Column(String(64), nullable=True)
    status = Column(String(30), nullable=False, default="pending_identity_review")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
