from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from database.base import Base


class CdasBookingMonitor(Base):
    __tablename__ = "cdas_booking_monitors"

    company_id = Column(
        UUID(as_uuid=True),
        ForeignKey("loan_companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    client_name = Column(String(200), nullable=False, index=True)
    client_reference = Column(String(120), nullable=True, index=True)

    item_code = Column(String(80), nullable=False)
    agency_name = Column(String(255), nullable=False, index=True)
    deduction_amount = Column(Numeric(15, 2), nullable=False)
    effective_date = Column(Date, nullable=False)
    expiry_date = Column(Date, nullable=False, index=True)
    reference_no = Column(String(255), nullable=True, index=True)
    source_status = Column(String(80), nullable=False, default="Active")

    booking_lead_months = Column(Integer, nullable=False, default=6)
    booking_open_date = Column(Date, nullable=False, index=True)
    alert_start_date = Column(Date, nullable=False, index=True)

    created_by_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    booked_at = Column(DateTime, nullable=True, index=True)
    booked_by_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    company = relationship("LoanCompany")
    created_by_user = relationship("User", foreign_keys=[created_by_user_id])
    booked_by_user = relationship("User", foreign_keys=[booked_by_user_id])
