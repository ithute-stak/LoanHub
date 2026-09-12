# database/models/lender_access.py
from sqlalchemy import Column, Enum, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from database.base import Base
from database.models.enums import AccessRequestStatus


class LenderAccessRequest(Base):
    __tablename__ = "lender_access_requests"

    loan_request_id = Column(UUID(as_uuid=True), ForeignKey("loan_requests.id"), nullable=False)
    company_id = Column(UUID(as_uuid=True), ForeignKey("loan_companies.id"), nullable=False)
    requested_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    status = Column(Enum(AccessRequestStatus), default=AccessRequestStatus.PENDING)
    message = Column(Text, nullable=True)

    loan_request = relationship("LoanRequest", back_populates="access_requests")
    company = relationship("LoanCompany")
    requested_by = relationship("User")