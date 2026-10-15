"""Persistent pad-signing records (not connected to live signing endpoints)."""
from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from database.base import Base


class ContractPadSigningSession(Base):
    __tablename__ = "contract_pad_signing_sessions"
    __table_args__ = (
        CheckConstraint("status IN ('created','consented','captured','completed','expired','cancelled')", name="ck_pad_session_status"),
        CheckConstraint("length(contract_hash) = 64", name="ck_pad_contract_hash_length"),
        Index("ix_pad_sessions_company_contract", "company_id", "contract_id"),
    )

    company_id = Column(UUID(as_uuid=True), ForeignKey("loan_companies.id", ondelete="RESTRICT"), nullable=False)
    contract_id = Column(UUID(as_uuid=True), ForeignKey("loan_contracts.id", ondelete="RESTRICT"), nullable=False)
    operator_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    contract_hash = Column(String(64), nullable=False)
    status = Column(String(24), nullable=False, default="created")
    verified_identity_at = Column(DateTime(timezone=True))
    consent_at = Column(DateTime(timezone=True))
    consent_version = Column(String(80))
    evidence_sha256 = Column(String(64))
    expires_at = Column(DateTime(timezone=True), nullable=False)
    evidence = relationship("ContractPadCaptureEvidence", uselist=False, back_populates="session")


class ContractPadCaptureEvidence(Base):
    __tablename__ = "contract_pad_capture_evidence"
    __table_args__ = (
        CheckConstraint("capture_source IN ('pointer','wacom_stu')", name="ck_pad_capture_source"),
        Index("ix_pad_capture_company", "company_id"),
    )

    company_id = Column(UUID(as_uuid=True), ForeignKey("loan_companies.id", ondelete="RESTRICT"), nullable=False)
    session_id = Column(UUID(as_uuid=True), ForeignKey("contract_pad_signing_sessions.id", ondelete="RESTRICT"), unique=True, nullable=False)
    evidence_sha256 = Column(String(64), nullable=False)
    encrypted_storage_key = Column(Text, nullable=False)
    capture_source = Column(String(24), nullable=False)
    session = relationship("ContractPadSigningSession", back_populates="evidence")
