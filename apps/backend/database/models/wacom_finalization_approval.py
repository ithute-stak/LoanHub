"""Two-person approval of Wacom evidence; not authority to sign by itself."""
from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, String, Text, UniqueConstraint, Index
from sqlalchemy.dialects.postgresql import UUID
from database.base import Base


class WacomFinalizationApproval(Base):
    __tablename__ = "wacom_finalization_approvals"
    __table_args__ = (
        CheckConstraint("status IN ('pending','approved','rejected','expired','consumed')",
                        name="ck_wacom_final_approval_state"),
        UniqueConstraint("intent_id", name="uq_wacom_finalization_intent"),
        Index("ix_wacom_finalization_company_status", "company_id", "status"),
    )
    company_id = Column(UUID(as_uuid=True), ForeignKey("loan_companies.id", ondelete="RESTRICT"), nullable=False)
    intent_id = Column(UUID(as_uuid=True), ForeignKey("wacom_document_intents.id", ondelete="RESTRICT"), nullable=False)
    contract_id = Column(UUID(as_uuid=True), ForeignKey("loan_contracts.id", ondelete="RESTRICT"), nullable=False)
    document_sha256 = Column(String(64), nullable=False)
    evidence_sha256 = Column(String(64), nullable=False)
    binding_sha256 = Column(String(64), nullable=False)
    status = Column(String(16), nullable=False, default="pending")
    requested_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    requested_at = Column(DateTime(timezone=True), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    decided_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"))
    decided_at = Column(DateTime(timezone=True))
    decision_reference = Column(String(180))
    decision_reason = Column(Text)
    consumed_at = Column(DateTime(timezone=True))
