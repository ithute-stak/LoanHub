from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID

from database.base import Base


class CdasBookingOpportunity(Base):
    __tablename__ = "cdas_booking_opportunities"

    company_id = Column(UUID(as_uuid=True), ForeignKey("loan_companies.id", ondelete="CASCADE"), nullable=False, index=True)
    client_name = Column(String(200), nullable=True, index=True)
    client_reference = Column(String(200), nullable=True, index=True)
    status = Column(String(30), nullable=False, default="monitoring", index=True)
    pipeline_stage = Column(String(40), nullable=False, default="identified", index=True)
    pipeline_updated_at = Column(DateTime, nullable=True)
    pipeline_updated_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    assigned_to_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    booking_lead_months = Column(Integer, nullable=False, default=6)
    alert_lead_days = Column(Integer, nullable=False, default=3)
    booking_open_date = Column(Date, nullable=True, index=True)
    alert_start_date = Column(Date, nullable=True, index=True)
    opportunity_agency_name = Column(String(255), nullable=True)
    opportunity_item_code = Column(String(100), nullable=True)
    opportunity_reference_no = Column(String(255), nullable=True, index=True)
    opportunity_effective_date = Column(Date, nullable=True)
    opportunity_expiry_date = Column(Date, nullable=True)
    opportunity_deduction_amount = Column(Numeric(18, 2), nullable=True)
    total_monthly_deductions = Column(Numeric(18, 2), nullable=False, default=0)
    own_monthly_deductions = Column(Numeric(18, 2), nullable=False, default=0)
    competitor_monthly_deductions = Column(Numeric(18, 2), nullable=False, default=0)
    analysis_snapshot = Column(JSONB, nullable=False, default=dict)
    booked_at = Column(DateTime, nullable=True)
    booked_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)


class CdasOpportunityContact(Base):
    __tablename__ = "cdas_opportunity_contacts"

    company_id = Column(UUID(as_uuid=True), ForeignKey("loan_companies.id", ondelete="CASCADE"), nullable=False, index=True)
    opportunity_id = Column(UUID(as_uuid=True), ForeignKey("cdas_booking_opportunities.id", ondelete="CASCADE"), nullable=False, index=True)
    channel = Column(String(30), nullable=False, index=True)
    outcome = Column(String(40), nullable=False, index=True)
    notes = Column(Text, nullable=True)
    contacted_at = Column(DateTime, nullable=False, index=True)
    next_follow_up_at = Column(DateTime, nullable=True, index=True)
    created_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)


class CdasAnalysisRecord(Base):
    """Immutable tenant-scoped archive of structured CDAS analyses.

    Raw pasted CDAS screen text is never stored. An exact duplicate analysis is
    represented once per company; materially changed analysis data gets a new
    history record and therefore a new reportable version.
    """

    __tablename__ = "cdas_analysis_records"
    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "analysis_fingerprint",
            name="uq_cdas_analysis_records_company_fingerprint",
        ),
    )

    company_id = Column(UUID(as_uuid=True), ForeignKey("loan_companies.id", ondelete="CASCADE"), nullable=False, index=True)
    analyzed_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    analyzed_by_name = Column(String(255), nullable=True)
    analyzed_by_role = Column(String(100), nullable=True)

    client_name = Column(String(200), nullable=True, index=True)
    client_reference = Column(String(200), nullable=True, index=True)
    employee_no = Column(String(200), nullable=True)
    nid = Column(String(200), nullable=True)
    employer = Column(String(255), nullable=True)

    current_agency_code = Column(String(100), nullable=True)
    current_agency_name = Column(String(255), nullable=True)
    decision = Column(String(30), nullable=False, index=True)

    assessed_available_amount = Column(Numeric(18, 2), nullable=True)
    amount_owing = Column(Numeric(18, 2), nullable=True)
    booking_months = Column(Integer, nullable=True)
    next_possible_booking_date = Column(Date, nullable=True, index=True)

    reported_active_monthly_deductions = Column(Numeric(18, 2), nullable=False, default=0)
    total_monthly_deductions = Column(Numeric(18, 2), nullable=False, default=0)
    data_quality_issue_count = Column(Integer, nullable=False, default=0)

    analysis_fingerprint = Column(String(64), nullable=False, index=True)
    analysis_snapshot = Column(JSONB, nullable=False, default=dict)
