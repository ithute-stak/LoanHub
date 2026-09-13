from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB, UUID

from database.base import Base


class CdasBookingOpportunity(Base):
    __tablename__ = "cdas_booking_opportunities"

    company_id = Column(UUID(as_uuid=True), ForeignKey("loan_companies.id", ondelete="CASCADE"), nullable=False, index=True)
    client_name = Column(String(200), nullable=True, index=True)
    client_reference = Column(String(200), nullable=True, index=True)
    status = Column(String(30), nullable=False, default="monitoring", index=True)
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
