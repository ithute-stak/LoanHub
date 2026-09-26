from __future__ import annotations

from decimal import Decimal

from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID

from database.base import Base


class CreditCommitteeCase(Base):
    """Human underwriting and committee-decision envelope for one application."""

    __tablename__ = "credit_committee_cases"
    __table_args__ = (
        UniqueConstraint("company_id", "application_id", name="uq_credit_committee_case_company_application"),
    )

    company_id = Column(UUID(as_uuid=True), ForeignKey("loan_companies.id", ondelete="CASCADE"), nullable=False, index=True)
    branch_id = Column(UUID(as_uuid=True), ForeignKey("company_branches.id", ondelete="SET NULL"), nullable=True, index=True)
    application_id = Column(UUID(as_uuid=True), ForeignKey("direct_loan_applications.id", ondelete="RESTRICT"), nullable=False, index=True)
    borrower_id = Column(UUID(as_uuid=True), ForeignKey("borrowers.id", ondelete="RESTRICT"), nullable=False, index=True)
    case_reference = Column(String(100), nullable=False, unique=True, index=True)
    status = Column(String(40), nullable=False, default="underwriting", index=True)
    required_votes = Column(Integer, nullable=False, default=2)
    approval_threshold_percent = Column(Numeric(6, 3), nullable=False, default=Decimal("66.667"))
    maker_checker_required = Column(Boolean, nullable=False, default=True)
    analyst_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    analyst_submitted_at = Column(DateTime, nullable=True)
    evidence_snapshot = Column(JSONB, nullable=False, default=dict)
    final_decision = Column(String(40), nullable=True, index=True)
    final_decision_reason = Column(Text, nullable=True)
    final_decided_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    final_decided_at = Column(DateTime, nullable=True)
    final_snapshot = Column(JSONB, nullable=False, default=dict)
    override_used = Column(Boolean, nullable=False, default=False)
    override_reason = Column(Text, nullable=True)
    locked_at = Column(DateTime, nullable=True)


class UnderwritingAssessment(Base):
    """Versioned analyst credit memo; prior submitted revisions remain immutable evidence."""

    __tablename__ = "underwriting_assessments"
    __table_args__ = (
        UniqueConstraint("case_id", "revision", name="uq_underwriting_assessment_case_revision"),
    )

    company_id = Column(UUID(as_uuid=True), ForeignKey("loan_companies.id", ondelete="CASCADE"), nullable=False, index=True)
    case_id = Column(UUID(as_uuid=True), ForeignKey("credit_committee_cases.id", ondelete="CASCADE"), nullable=False, index=True)
    application_id = Column(UUID(as_uuid=True), ForeignKey("direct_loan_applications.id", ondelete="RESTRICT"), nullable=False, index=True)
    borrower_id = Column(UUID(as_uuid=True), ForeignKey("borrowers.id", ondelete="RESTRICT"), nullable=False, index=True)
    revision = Column(Integer, nullable=False, default=1)
    status = Column(String(30), nullable=False, default="submitted", index=True)
    analyst_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    requested_amount = Column(Numeric(15, 2), nullable=False, default=0)
    proposed_amount = Column(Numeric(15, 2), nullable=False, default=0)
    proposed_installment = Column(Numeric(15, 2), nullable=False, default=0)
    proposed_term = Column(Integer, nullable=False, default=0)
    verified_income = Column(Numeric(15, 2), nullable=False, default=0)
    household_expenses = Column(Numeric(15, 2), nullable=False, default=0)
    existing_debt_installments = Column(Numeric(15, 2), nullable=False, default=0)
    dti_percent = Column(Numeric(8, 3), nullable=False, default=0)
    affordability_headroom = Column(Numeric(15, 2), nullable=False, default=0)
    bureau_score = Column(Integer, nullable=True)
    bureau_risk_grade = Column(String(40), nullable=True)
    kyc_status = Column(String(40), nullable=True)
    risk_score = Column(Numeric(8, 3), nullable=True)
    risk_grade = Column(String(30), nullable=False, default="medium", index=True)
    recommendation = Column(String(40), nullable=False, index=True)
    rationale = Column(Text, nullable=False)
    strengths = Column(JSONB, nullable=False, default=list)
    weaknesses = Column(JSONB, nullable=False, default=list)
    exceptions = Column(JSONB, nullable=False, default=list)
    mitigants = Column(JSONB, nullable=False, default=list)
    proposed_conditions = Column(JSONB, nullable=False, default=list)
    evidence_snapshot = Column(JSONB, nullable=False, default=dict)
    submitted_at = Column(DateTime, nullable=False)


class CreditCommitteeVote(Base):
    """One current vote per committee member; changes are preserved in the event ledger."""

    __tablename__ = "credit_committee_votes"
    __table_args__ = (
        UniqueConstraint("case_id", "user_id", name="uq_credit_committee_vote_case_user"),
    )

    company_id = Column(UUID(as_uuid=True), ForeignKey("loan_companies.id", ondelete="CASCADE"), nullable=False, index=True)
    case_id = Column(UUID(as_uuid=True), ForeignKey("credit_committee_cases.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    role = Column(String(60), nullable=False)
    decision = Column(String(40), nullable=False, index=True)
    rationale = Column(Text, nullable=False)
    conditions = Column(JSONB, nullable=False, default=list)
    voted_at = Column(DateTime, nullable=False)


class CreditCommitteeCondition(Base):
    """Decision condition with explicit satisfaction/waiver evidence."""

    __tablename__ = "credit_committee_conditions"

    company_id = Column(UUID(as_uuid=True), ForeignKey("loan_companies.id", ondelete="CASCADE"), nullable=False, index=True)
    case_id = Column(UUID(as_uuid=True), ForeignKey("credit_committee_cases.id", ondelete="CASCADE"), nullable=False, index=True)
    source = Column(String(40), nullable=False, default="committee")
    condition_type = Column(String(40), nullable=False, default="pre_disbursement", index=True)
    title = Column(String(220), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(String(30), nullable=False, default="open", index=True)
    due_date = Column(Date, nullable=True)
    evidence_note = Column(Text, nullable=True)
    created_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    resolved_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    resolved_at = Column(DateTime, nullable=True)
    waiver_reason = Column(Text, nullable=True)


class CreditCommitteeEvent(Base):
    """Append-only committee audit event."""

    __tablename__ = "credit_committee_events"

    company_id = Column(UUID(as_uuid=True), ForeignKey("loan_companies.id", ondelete="CASCADE"), nullable=False, index=True)
    case_id = Column(UUID(as_uuid=True), ForeignKey("credit_committee_cases.id", ondelete="CASCADE"), nullable=False, index=True)
    event_type = Column(String(60), nullable=False, index=True)
    actor_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    payload = Column(JSONB, nullable=False, default=dict)
