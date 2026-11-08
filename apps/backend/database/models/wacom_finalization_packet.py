"""One archived immutable reviewed Wacom evidence packet per approval.

This is NOT a legally signed loan contract.
"""
from sqlalchemy import Column, DateTime, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from database.base import Base


class WacomFinalizationPacket(Base):
    __tablename__ = "wacom_finalization_packets"
    __table_args__ = (
        UniqueConstraint("approval_id", name="uq_wacom_packet_approval"),
        UniqueConstraint("intent_id", name="uq_wacom_packet_intent"),
        UniqueConstraint("contract_id", name="uq_wacom_packet_contract"),
        Index("ix_wacom_packet_company", "company_id", "created_at"),
    )
    company_id = Column(UUID(as_uuid=True), ForeignKey("loan_companies.id", ondelete="RESTRICT"), nullable=False)
    approval_id = Column(UUID(as_uuid=True), ForeignKey("wacom_finalization_approvals.id", ondelete="RESTRICT"), nullable=False)
    intent_id = Column(UUID(as_uuid=True), ForeignKey("wacom_document_intents.id", ondelete="RESTRICT"), nullable=False)
    contract_id = Column(UUID(as_uuid=True), ForeignKey("loan_contracts.id", ondelete="RESTRICT"), nullable=False)
    packet_file_id = Column(UUID(as_uuid=True), ForeignKey("managed_files.id", ondelete="RESTRICT"), nullable=False)
    source_sha256 = Column(String(64), nullable=False)
    handwriting_sha256 = Column(String(64), nullable=False)
    packet_sha256 = Column(String(64), nullable=False)
    created_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    archived_at = Column(DateTime(timezone=True), nullable=False)
