"""Separate, one-time Wacom contract execution authorization.

This table is not itself an executed signature, and storing an approval
does not change contract state or release any signing key.
"""
from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from database.base import Base


class WacomExecutionAuthorization(Base):
    __tablename__ = "wacom_execution_authorizations"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending','approved','rejected','expired','consumed','cancelled')",
            name="ck_wacom_execution_authorization_status",
        ),
        UniqueConstraint("intent_id", name="uq_wacom_execution_auth_intent"),
        UniqueConstraint("contract_id", name="uq_wacom_execution_auth_contract"),
        Index("ix_wacom_execution_auth_company_status", "company_id", "status"),
        CheckConstraint(
            "length(document_sha256) = 64 AND length(evidence_sha256) = 64 "
            "AND length(binding_sha256) = 64",
            name="ck_wacom_execution_auth_hash_lengths",
        ),
    )
    company_id = Column(UUID(as_uuid=True), ForeignKey("loan_companies.id", ondelete="RESTRICT"), nullable=False)
    intent_id = Column(UUID(as_uuid=True), ForeignKey("wacom_document_intents.id", ondelete="RESTRICT"), nullable=False)
    contract_id = Column(UUID(as_uuid=True), ForeignKey("loan_contracts.id", ondelete="RESTRICT"), nullable=False)
    packet_id = Column(UUID(as_uuid=True), ForeignKey("wacom_finalization_packets.id", ondelete="RESTRICT"), nullable=False)
    document_sha256 = Column(String(64), nullable=False)
    evidence_sha256 = Column(String(64), nullable=False)
    binding_sha256 = Column(String(64), nullable=False)
    status = Column(String(16), nullable=False, default="pending")
    requested_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    requested_at = Column(DateTime(timezone=True), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    authorized_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"))
    authorized_at = Column(DateTime(timezone=True))
    authorization_reference = Column(String(180))
    consumed_at = Column(DateTime(timezone=True))
    consumed_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"))
