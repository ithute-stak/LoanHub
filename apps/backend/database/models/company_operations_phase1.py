from __future__ import annotations

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from database.base import Base


class CRMRelationshipCase(Base):
    """Native CRM relationship case linked to a borrower and optionally a loan."""

    __tablename__ = "crm_relationship_cases"
    __table_args__ = (
        UniqueConstraint("company_id", "reference", name="uq_crm_relationship_case_company_reference"),
    )

    company_id = Column(UUID(as_uuid=True), ForeignKey("loan_companies.id", ondelete="CASCADE"), nullable=False, index=True)
    branch_id = Column(UUID(as_uuid=True), ForeignKey("company_branches.id", ondelete="SET NULL"), nullable=True, index=True)
    borrower_id = Column(UUID(as_uuid=True), ForeignKey("borrowers.id", ondelete="CASCADE"), nullable=False, index=True)
    loan_id = Column(UUID(as_uuid=True), ForeignKey("client_company_loan.id", ondelete="SET NULL"), nullable=True, index=True)
    reference = Column(String(100), nullable=False, index=True)
    relationship_stage = Column(String(40), nullable=False, default="active", index=True)
    segment = Column(String(60), nullable=True, index=True)
    status = Column(String(30), nullable=False, default="open", index=True)
    assigned_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    next_action_at = Column(DateTime, nullable=True, index=True)
    last_contact_at = Column(DateTime, nullable=True)
    contact_preference = Column(String(40), nullable=True)
    retention_risk = Column(String(30), nullable=True, index=True)
    notes = Column(Text, nullable=True)
    metadata_json = Column(JSONB, nullable=False, default=dict)

    borrower = relationship("Borrower")
    loan = relationship("ClientCompanyLoan")
    assigned_user = relationship("User", foreign_keys=[assigned_user_id])


class CollateralAsset(Base):
    """Security/collateral register with ownership, valuation and release controls."""

    __tablename__ = "collateral_assets"
    __table_args__ = (
        UniqueConstraint("company_id", "reference", name="uq_collateral_asset_company_reference"),
    )

    company_id = Column(UUID(as_uuid=True), ForeignKey("loan_companies.id", ondelete="CASCADE"), nullable=False, index=True)
    branch_id = Column(UUID(as_uuid=True), ForeignKey("company_branches.id", ondelete="SET NULL"), nullable=True, index=True)
    borrower_id = Column(UUID(as_uuid=True), ForeignKey("borrowers.id", ondelete="CASCADE"), nullable=False, index=True)
    loan_id = Column(UUID(as_uuid=True), ForeignKey("client_company_loan.id", ondelete="SET NULL"), nullable=True, index=True)
    reference = Column(String(100), nullable=False, index=True)
    asset_type = Column(String(60), nullable=False, index=True)
    description = Column(Text, nullable=False)
    ownership_name = Column(String(240), nullable=False)
    ownership_reference = Column(String(180), nullable=True)
    valuation_amount = Column(Numeric(18, 2), nullable=True)
    valuation_date = Column(DateTime, nullable=True)
    valuer_name = Column(String(240), nullable=True)
    currency = Column(String(3), nullable=False, default="LSL")
    status = Column(String(30), nullable=False, default="held", index=True)
    perfected = Column(Boolean, nullable=False, default=False, index=True)
    perfection_reference = Column(String(180), nullable=True)
    insured = Column(Boolean, nullable=False, default=False)
    insurance_expiry_at = Column(DateTime, nullable=True)
    release_requested_at = Column(DateTime, nullable=True)
    released_at = Column(DateTime, nullable=True)
    released_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    metadata_json = Column(JSONB, nullable=False, default=dict)

    borrower = relationship("Borrower")
    loan = relationship("ClientCompanyLoan")
    released_by = relationship("User", foreign_keys=[released_by_user_id])


class LegalRecoveryMatter(Base):
    """Legal-recovery matter tied to a borrower/loan and optionally an existing collection case."""

    __tablename__ = "legal_recovery_matters"
    __table_args__ = (
        UniqueConstraint("company_id", "reference", name="uq_legal_recovery_matter_company_reference"),
    )

    company_id = Column(UUID(as_uuid=True), ForeignKey("loan_companies.id", ondelete="CASCADE"), nullable=False, index=True)
    branch_id = Column(UUID(as_uuid=True), ForeignKey("company_branches.id", ondelete="SET NULL"), nullable=True, index=True)
    borrower_id = Column(UUID(as_uuid=True), ForeignKey("borrowers.id", ondelete="CASCADE"), nullable=False, index=True)
    loan_id = Column(UUID(as_uuid=True), ForeignKey("client_company_loan.id", ondelete="CASCADE"), nullable=False, index=True)
    collection_case_id = Column(UUID(as_uuid=True), ForeignKey("collection_cases.id", ondelete="SET NULL"), nullable=True, index=True)
    reference = Column(String(100), nullable=False, index=True)
    status = Column(String(40), nullable=False, default="pre_legal", index=True)
    legal_stage = Column(String(50), nullable=False, default="pre_action", index=True)
    counsel_name = Column(String(240), nullable=True)
    court_name = Column(String(240), nullable=True)
    court_case_number = Column(String(160), nullable=True, index=True)
    claim_amount = Column(Numeric(18, 2), nullable=True)
    legal_costs = Column(Numeric(18, 2), nullable=False, default=0)
    currency = Column(String(3), nullable=False, default="LSL")
    next_court_at = Column(DateTime, nullable=True, index=True)
    limitation_deadline_at = Column(DateTime, nullable=True, index=True)
    assigned_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    outcome = Column(String(80), nullable=True)
    notes = Column(Text, nullable=True)
    metadata_json = Column(JSONB, nullable=False, default=dict)

    borrower = relationship("Borrower")
    loan = relationship("ClientCompanyLoan")
    collection_case = relationship("CollectionCase")
    assigned_user = relationship("User", foreign_keys=[assigned_user_id])


class ComplaintCase(Base):
    """Customer complaint with SLA, escalation and resolution evidence."""

    __tablename__ = "complaint_cases"
    __table_args__ = (
        UniqueConstraint("company_id", "reference", name="uq_complaint_case_company_reference"),
    )

    company_id = Column(UUID(as_uuid=True), ForeignKey("loan_companies.id", ondelete="CASCADE"), nullable=False, index=True)
    branch_id = Column(UUID(as_uuid=True), ForeignKey("company_branches.id", ondelete="SET NULL"), nullable=True, index=True)
    borrower_id = Column(UUID(as_uuid=True), ForeignKey("borrowers.id", ondelete="SET NULL"), nullable=True, index=True)
    loan_id = Column(UUID(as_uuid=True), ForeignKey("client_company_loan.id", ondelete="SET NULL"), nullable=True, index=True)
    reference = Column(String(100), nullable=False, index=True)
    category = Column(String(80), nullable=False, index=True)
    channel = Column(String(40), nullable=False, default="internal", index=True)
    subject = Column(String(240), nullable=False)
    description = Column(Text, nullable=False)
    severity = Column(String(30), nullable=False, default="normal", index=True)
    status = Column(String(40), nullable=False, default="open", index=True)
    assigned_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    acknowledged_at = Column(DateTime, nullable=True)
    sla_due_at = Column(DateTime, nullable=False, index=True)
    escalated_at = Column(DateTime, nullable=True)
    resolved_at = Column(DateTime, nullable=True)
    resolution = Column(Text, nullable=True)
    root_cause = Column(Text, nullable=True)
    remediation = Column(Text, nullable=True)
    regulatory_reportable = Column(Boolean, nullable=False, default=False, index=True)
    metadata_json = Column(JSONB, nullable=False, default=dict)

    borrower = relationship("Borrower")
    loan = relationship("ClientCompanyLoan")
    assigned_user = relationship("User", foreign_keys=[assigned_user_id])


class CompanyOperationEvent(Base):
    """Append-only event trail shared by the specialised phase-one operating workflows."""

    __tablename__ = "company_operation_events"

    company_id = Column(UUID(as_uuid=True), ForeignKey("loan_companies.id", ondelete="CASCADE"), nullable=False, index=True)
    branch_id = Column(UUID(as_uuid=True), ForeignKey("company_branches.id", ondelete="SET NULL"), nullable=True, index=True)
    module = Column(String(40), nullable=False, index=True)
    record_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    event_type = Column(String(80), nullable=False, index=True)
    actor_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    payload = Column(JSONB, nullable=False, default=dict)

    actor = relationship("User", foreign_keys=[actor_user_id])
