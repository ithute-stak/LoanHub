from __future__ import annotations

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from database.base import Base


class CollectionTreatmentPolicy(Base):
    """Tenant-owned treatment policy used by the automated recovery engine."""

    __tablename__ = "collection_treatment_policies"
    __table_args__ = (
        UniqueConstraint("company_id", "name", name="uq_collection_treatment_policy_company_name"),
    )

    company_id = Column(UUID(as_uuid=True), ForeignKey("loan_companies.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(160), nullable=False)
    is_active = Column(Boolean, nullable=False, default=True, index=True)
    version = Column(Integer, nullable=False, default=1)
    strategy = Column(JSONB, nullable=False, default=dict)
    configured_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    company = relationship("LoanCompany")
    configured_by = relationship("User", foreign_keys=[configured_by_user_id])


class CollectionWorkItem(Base):
    """One actionable recovery task produced for an existing collection case."""

    __tablename__ = "collection_work_items"
    __table_args__ = (
        UniqueConstraint("case_id", "deduplication_key", name="uq_collection_work_item_case_dedup"),
    )

    company_id = Column(UUID(as_uuid=True), ForeignKey("loan_companies.id", ondelete="CASCADE"), nullable=False, index=True)
    branch_id = Column(UUID(as_uuid=True), ForeignKey("company_branches.id", ondelete="SET NULL"), nullable=True, index=True)
    case_id = Column(UUID(as_uuid=True), ForeignKey("collection_cases.id", ondelete="CASCADE"), nullable=False, index=True)
    loan_id = Column(UUID(as_uuid=True), ForeignKey("client_company_loan.id", ondelete="CASCADE"), nullable=False, index=True)
    borrower_id = Column(UUID(as_uuid=True), ForeignKey("borrowers.id", ondelete="CASCADE"), nullable=False, index=True)
    assigned_to_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    deduplication_key = Column(String(180), nullable=False)
    action_type = Column(String(60), nullable=False, index=True)
    treatment_code = Column(String(80), nullable=False, index=True)
    recovery_path = Column(String(60), nullable=False, default="direct_collection", index=True)
    priority_score = Column(Numeric(10, 3), nullable=False, default=0, index=True)
    priority = Column(String(30), nullable=False, default="normal", index=True)
    reason = Column(Text, nullable=True)
    due_at = Column(DateTime, nullable=False, index=True)
    status = Column(String(30), nullable=False, default="open", index=True)
    attempt_count = Column(Integer, nullable=False, default=0)
    source = Column(String(40), nullable=False, default="automation")
    context_snapshot = Column(JSONB, nullable=False, default=dict)
    completed_at = Column(DateTime, nullable=True)
    completed_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    completion_notes = Column(Text, nullable=True)

    case = relationship("CollectionCase", foreign_keys=[case_id])
    loan = relationship("ClientCompanyLoan", foreign_keys=[loan_id])
    borrower = relationship("Borrower", foreign_keys=[borrower_id])
    assigned_to = relationship("User", foreign_keys=[assigned_to_user_id])
    completed_by = relationship("User", foreign_keys=[completed_by_user_id])


class CollectionAutomationRun(Base):
    """Immutable-ish summary of one company recovery-engine execution."""

    __tablename__ = "collection_automation_runs"

    company_id = Column(UUID(as_uuid=True), ForeignKey("loan_companies.id", ondelete="CASCADE"), nullable=False, index=True)
    branch_id = Column(UUID(as_uuid=True), ForeignKey("company_branches.id", ondelete="SET NULL"), nullable=True, index=True)
    run_reference = Column(String(100), nullable=False, unique=True, index=True)
    status = Column(String(30), nullable=False, default="completed", index=True)
    cases_checked = Column(Integer, nullable=False, default=0)
    work_items_created = Column(Integer, nullable=False, default=0)
    work_items_updated = Column(Integer, nullable=False, default=0)
    broken_promises_detected = Column(Integer, nullable=False, default=0)
    legal_ready_cases = Column(Integer, nullable=False, default=0)
    summary = Column(JSONB, nullable=False, default=dict)
    started_at = Column(DateTime, nullable=False)
    completed_at = Column(DateTime, nullable=False)
    triggered_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    company = relationship("LoanCompany")
    triggered_by = relationship("User", foreign_keys=[triggered_by_user_id])
