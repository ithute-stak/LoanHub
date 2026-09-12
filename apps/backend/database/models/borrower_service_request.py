from sqlalchemy import Column, DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from database.base import Base


class BorrowerServiceRequest(Base):
    """A borrower-initiated, lender-addressed servicing workflow.

    This table intentionally stores the request/response workflow only. Loan,
    repayment and settlement balances continue to come from the authoritative
    lending ledger rather than being duplicated here.
    """

    __tablename__ = "borrower_service_requests"

    borrower_id = Column(
        UUID(as_uuid=True),
        ForeignKey("borrowers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    company_id = Column(
        UUID(as_uuid=True),
        ForeignKey("loan_companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    loan_id = Column(
        UUID(as_uuid=True),
        ForeignKey("client_company_loan.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    request_type = Column(String(60), nullable=False, index=True)
    status = Column(String(30), nullable=False, default="submitted", index=True)
    subject = Column(String(180), nullable=False)
    details = Column(Text, nullable=True)
    requested_value = Column(Numeric(15, 2), nullable=True)

    company_response = Column(Text, nullable=True)
    responded_by_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    responded_at = Column(DateTime, nullable=True)

    borrower = relationship("Borrower")
    company = relationship("LoanCompany")
    loan = relationship("ClientCompanyLoan")
    responded_by = relationship("User", foreign_keys=[responded_by_user_id])
