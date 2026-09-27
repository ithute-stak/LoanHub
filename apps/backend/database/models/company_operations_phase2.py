from __future__ import annotations

from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from database.base import Base


class ProcurementVendor(Base):
    __tablename__ = "procurement_vendors"
    __table_args__ = (UniqueConstraint("company_id", "vendor_code", name="uq_procurement_vendor_company_code"),)

    company_id = Column(UUID(as_uuid=True), ForeignKey("loan_companies.id", ondelete="CASCADE"), nullable=False, index=True)
    vendor_code = Column(String(80), nullable=False, index=True)
    legal_name = Column(String(240), nullable=False, index=True)
    registration_number = Column(String(120), nullable=True)
    tax_number = Column(String(120), nullable=True)
    contact_name = Column(String(180), nullable=True)
    contact_email = Column(String(240), nullable=True)
    contact_phone = Column(String(80), nullable=True)
    category = Column(String(100), nullable=True, index=True)
    status = Column(String(30), nullable=False, default="active", index=True)
    risk_rating = Column(String(30), nullable=True, index=True)
    due_diligence_completed = Column(Boolean, nullable=False, default=False, index=True)
    due_diligence_expires_at = Column(DateTime, nullable=True, index=True)
    metadata_json = Column(JSONB, nullable=False, default=dict)


class ProcurementRequest(Base):
    __tablename__ = "procurement_requests"
    __table_args__ = (UniqueConstraint("company_id", "reference", name="uq_procurement_request_company_reference"),)

    company_id = Column(UUID(as_uuid=True), ForeignKey("loan_companies.id", ondelete="CASCADE"), nullable=False, index=True)
    branch_id = Column(UUID(as_uuid=True), ForeignKey("company_branches.id", ondelete="SET NULL"), nullable=True, index=True)
    vendor_id = Column(UUID(as_uuid=True), ForeignKey("procurement_vendors.id", ondelete="SET NULL"), nullable=True, index=True)
    reference = Column(String(100), nullable=False, index=True)
    title = Column(String(240), nullable=False)
    description = Column(Text, nullable=True)
    category = Column(String(100), nullable=True, index=True)
    amount = Column(Numeric(18, 2), nullable=False, default=0)
    currency = Column(String(3), nullable=False, default="LSL")
    status = Column(String(40), nullable=False, default="draft", index=True)
    requested_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    approved_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    needed_by = Column(Date, nullable=True, index=True)
    submitted_at = Column(DateTime, nullable=True)
    approved_at = Column(DateTime, nullable=True)
    rejected_at = Column(DateTime, nullable=True)
    decision_note = Column(Text, nullable=True)
    metadata_json = Column(JSONB, nullable=False, default=dict)

    vendor = relationship("ProcurementVendor")
    requested_by = relationship("User", foreign_keys=[requested_by_user_id])
    approved_by = relationship("User", foreign_keys=[approved_by_user_id])


class CompanyBudgetPlan(Base):
    __tablename__ = "company_budget_plans"
    __table_args__ = (UniqueConstraint("company_id", "fiscal_year", "version", name="uq_company_budget_plan_year_version"),)

    company_id = Column(UUID(as_uuid=True), ForeignKey("loan_companies.id", ondelete="CASCADE"), nullable=False, index=True)
    branch_id = Column(UUID(as_uuid=True), ForeignKey("company_branches.id", ondelete="SET NULL"), nullable=True, index=True)
    fiscal_year = Column(String(20), nullable=False, index=True)
    version = Column(String(40), nullable=False, default="baseline")
    status = Column(String(30), nullable=False, default="draft", index=True)
    currency = Column(String(3), nullable=False, default="LSL")
    notes = Column(Text, nullable=True)
    approved_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    approved_at = Column(DateTime, nullable=True)
    metadata_json = Column(JSONB, nullable=False, default=dict)

    approved_by = relationship("User", foreign_keys=[approved_by_user_id])


class CompanyBudgetLine(Base):
    __tablename__ = "company_budget_lines"
    __table_args__ = (UniqueConstraint("plan_id", "cost_centre", "account_code", "period", name="uq_company_budget_line_dimension"),)

    plan_id = Column(UUID(as_uuid=True), ForeignKey("company_budget_plans.id", ondelete="CASCADE"), nullable=False, index=True)
    company_id = Column(UUID(as_uuid=True), ForeignKey("loan_companies.id", ondelete="CASCADE"), nullable=False, index=True)
    branch_id = Column(UUID(as_uuid=True), ForeignKey("company_branches.id", ondelete="SET NULL"), nullable=True, index=True)
    cost_centre = Column(String(100), nullable=False, index=True)
    account_code = Column(String(100), nullable=False, index=True)
    period = Column(String(20), nullable=False, index=True)
    budget_amount = Column(Numeric(18, 2), nullable=False, default=0)
    forecast_amount = Column(Numeric(18, 2), nullable=False, default=0)
    actual_amount = Column(Numeric(18, 2), nullable=False, default=0)
    note = Column(Text, nullable=True)

    plan = relationship("CompanyBudgetPlan")


class InternalAuditEngagement(Base):
    __tablename__ = "internal_audit_engagements"
    __table_args__ = (UniqueConstraint("company_id", "reference", name="uq_internal_audit_engagement_company_reference"),)

    company_id = Column(UUID(as_uuid=True), ForeignKey("loan_companies.id", ondelete="CASCADE"), nullable=False, index=True)
    branch_id = Column(UUID(as_uuid=True), ForeignKey("company_branches.id", ondelete="SET NULL"), nullable=True, index=True)
    reference = Column(String(100), nullable=False, index=True)
    title = Column(String(240), nullable=False)
    audit_area = Column(String(120), nullable=False, index=True)
    risk_rating = Column(String(30), nullable=True, index=True)
    status = Column(String(40), nullable=False, default="planned", index=True)
    lead_auditor_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    planned_start = Column(Date, nullable=True)
    planned_end = Column(Date, nullable=True)
    started_at = Column(DateTime, nullable=True)
    closed_at = Column(DateTime, nullable=True)
    scope = Column(Text, nullable=True)
    conclusion = Column(Text, nullable=True)
    metadata_json = Column(JSONB, nullable=False, default=dict)

    lead_auditor = relationship("User", foreign_keys=[lead_auditor_user_id])


class InternalAuditFinding(Base):
    __tablename__ = "internal_audit_findings"
    __table_args__ = (UniqueConstraint("engagement_id", "finding_number", name="uq_internal_audit_finding_number"),)

    engagement_id = Column(UUID(as_uuid=True), ForeignKey("internal_audit_engagements.id", ondelete="CASCADE"), nullable=False, index=True)
    company_id = Column(UUID(as_uuid=True), ForeignKey("loan_companies.id", ondelete="CASCADE"), nullable=False, index=True)
    branch_id = Column(UUID(as_uuid=True), ForeignKey("company_branches.id", ondelete="SET NULL"), nullable=True, index=True)
    finding_number = Column(String(40), nullable=False, index=True)
    title = Column(String(240), nullable=False)
    severity = Column(String(30), nullable=False, default="medium", index=True)
    status = Column(String(30), nullable=False, default="open", index=True)
    observation = Column(Text, nullable=False)
    recommendation = Column(Text, nullable=True)
    management_response = Column(Text, nullable=True)
    owner_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    due_at = Column(DateTime, nullable=True, index=True)
    remediated_at = Column(DateTime, nullable=True)
    closure_evidence = Column(Text, nullable=True)
    verified_at = Column(DateTime, nullable=True)
    verified_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    engagement = relationship("InternalAuditEngagement")
    owner = relationship("User", foreign_keys=[owner_user_id])
    verified_by = relationship("User", foreign_keys=[verified_by_user_id])
