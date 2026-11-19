"""Dedicated borrower-bound CDAS affordability consent review evidence.

A generic borrower_document.is_verified flag is NOT sufficient to approve this
record. No route in this phase creates an approved consent automatically.
"""
from sqlalchemy import Boolean, CheckConstraint, Column, DateTime, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import UUID
from database.base import Base


class CdasAffordabilityConsentEvidence(Base):
    __tablename__ = "cdas_affordability_consent_evidence"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending','approved','rejected','revoked')",
            name="ck_cdas_aff_consent_status",
        ),
        Index("ix_cdas_aff_consent_company_borrower", "company_id", "borrower_id"),
        Index("ix_cdas_aff_consent_company_reference", "company_id", "reference", unique=True),
    )

    company_id = Column(UUID(as_uuid=True), ForeignKey("loan_companies.id", ondelete="RESTRICT"), nullable=False)
    borrower_id = Column(UUID(as_uuid=True), ForeignKey("borrowers.id", ondelete="RESTRICT"), nullable=False)
    document_id = Column(UUID(as_uuid=True), ForeignKey("borrower_documents.id", ondelete="RESTRICT"), nullable=False)
    employee_number = Column(String(100), nullable=False)
    reference = Column(String(200), nullable=False)
    purpose = Column(String(100), nullable=False, default="cdas_government_employee_affordability")
    status = Column(String(20), nullable=False, default="pending")
    document_sha256 = Column(String(64), nullable=True)
    borrower_authorization_confirmed = Column(Boolean, nullable=False, default=False)
    submitted_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    verified_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    verified_at = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)
