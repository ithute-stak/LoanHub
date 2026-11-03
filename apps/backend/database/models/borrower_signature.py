"""Borrower-owned reusable signature profile and per-contract use authorization.

No authorization is inferred from a saved image. These records are only
populated by a separately verified, consented signing workflow.
"""
from sqlalchemy import Boolean, CheckConstraint, Column, DateTime, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from database.base import Base


class BorrowerSavedSignature(Base):
    __tablename__ = "borrower_saved_signatures"
    __table_args__ = (
        CheckConstraint("status IN ('active','revoked')", name="ck_saved_signature_status"),
        CheckConstraint("length(evidence_sha256) = 64", name="ck_saved_signature_hash_length"),
        Index("ix_saved_signature_tenant_borrower", "company_id", "borrower_id"),
    )

    company_id = Column(UUID(as_uuid=True), ForeignKey("loan_companies.id", ondelete="RESTRICT"), nullable=False)
    borrower_id = Column(UUID(as_uuid=True), ForeignKey("borrowers.id", ondelete="RESTRICT"), nullable=False)
    source_session_id = Column(UUID(as_uuid=True), ForeignKey("contract_pad_signing_sessions.id", ondelete="RESTRICT"), nullable=False, unique=True)
    encrypted_storage_key = Column(Text, nullable=False)
    evidence_sha256 = Column(String(64), nullable=False)
    capture_source = Column(String(24), nullable=False)
    status = Column(String(16), nullable=False, default="active")
    reuse_opt_in_at = Column(DateTime(timezone=True), nullable=False)
    revoked_at = Column(DateTime(timezone=True))


class BorrowerSignatureUseAuthorization(Base):
    __tablename__ = "borrower_signature_use_authorizations"
    __table_args__ = (
        UniqueConstraint("company_id", "contract_id", name="uq_signature_use_company_contract"),
        CheckConstraint("status IN ('authorized','used','cancelled')", name="ck_signature_use_status"),
        CheckConstraint("length(contract_hash) = 64", name="ck_signature_use_contract_hash"),
        Index("ix_signature_use_tenant_borrower", "company_id", "borrower_id"),
    )

    company_id = Column(UUID(as_uuid=True), ForeignKey("loan_companies.id", ondelete="RESTRICT"), nullable=False)
    borrower_id = Column(UUID(as_uuid=True), ForeignKey("borrowers.id", ondelete="RESTRICT"), nullable=False)
    signature_id = Column(UUID(as_uuid=True), ForeignKey("borrower_saved_signatures.id", ondelete="RESTRICT"), nullable=False)
    contract_id = Column(UUID(as_uuid=True), ForeignKey("loan_contracts.id", ondelete="RESTRICT"), nullable=False)
    session_id = Column(UUID(as_uuid=True), ForeignKey("contract_pad_signing_sessions.id", ondelete="RESTRICT"), nullable=False, unique=True)
    contract_hash = Column(String(64), nullable=False)
    status = Column(String(16), nullable=False, default="authorized")
    verified_identity_at = Column(DateTime(timezone=True), nullable=False)
    explicit_consent_at = Column(DateTime(timezone=True), nullable=False)
    consumed_at = Column(DateTime(timezone=True))
