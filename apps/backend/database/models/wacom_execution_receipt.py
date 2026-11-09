"""Exactly-once reserved Wacom execution receipt.

A receipt is only a database record. No route currently creates one and no
receipt by itself is proof of a legally executed contract. Storage / contract
mutation must be implemented in a separately reviewed atomic transaction.
"""
from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from database.base import Base


class WacomExecutionReceipt(Base):
    __tablename__ = "wacom_execution_receipts"
    __table_args__ = (
        UniqueConstraint("company_id", "contract_id", name="uq_wacom_exec_receipt_company_contract"),
        UniqueConstraint("authorization_id", name="uq_wacom_exec_receipt_authorization"),
        UniqueConstraint("intent_id", name="uq_wacom_exec_receipt_intent"),
        CheckConstraint(
            "status IN ('reserved','executed','aborted')",
            name="ck_wacom_execution_receipt_status",
        ),
        CheckConstraint(
            "length(document_sha256) = 64 AND length(evidence_sha256) = 64 "
            "AND length(binding_sha256) = 64",
            name="ck_wacom_execution_receipt_hash_length",
        ),
        CheckConstraint(
            "(status <> 'executed') OR "
            "(executed_file_id IS NOT NULL AND executed_pdf_sha256 IS NOT NULL "
            "AND executed_at IS NOT NULL AND length(executed_pdf_sha256) = 64)",
            name="ck_wacom_execution_receipt_completed",
        ),
        Index("ix_wacom_execution_receipt_company", "company_id", "status"),
    )
    company_id = Column(UUID(as_uuid=True), ForeignKey("loan_companies.id", ondelete="RESTRICT"), nullable=False)
    contract_id = Column(UUID(as_uuid=True), ForeignKey("loan_contracts.id", ondelete="RESTRICT"), nullable=False)
    intent_id = Column(UUID(as_uuid=True), ForeignKey("wacom_document_intents.id", ondelete="RESTRICT"), nullable=False)
    authorization_id = Column(UUID(as_uuid=True), ForeignKey("wacom_execution_authorizations.id", ondelete="RESTRICT"), nullable=False)
    packet_id = Column(UUID(as_uuid=True), ForeignKey("wacom_finalization_packets.id", ondelete="RESTRICT"), nullable=False)
    document_sha256 = Column(String(64), nullable=False)
    evidence_sha256 = Column(String(64), nullable=False)
    binding_sha256 = Column(String(64), nullable=False)
    status = Column(String(16), nullable=False, default="reserved")
    reserved_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    reserved_at = Column(DateTime(timezone=True), nullable=False)
    executed_file_id = Column(UUID(as_uuid=True), ForeignKey("managed_files.id", ondelete="RESTRICT"))
    executed_pdf_sha256 = Column(String(64))
    executed_at = Column(DateTime(timezone=True))
