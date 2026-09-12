from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer, Numeric, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from database.base import Base
from database.models.enums import OfferStatus


class LoanOffer(Base):
    __tablename__ = "loan_offers"
    __table_args__ = (
        UniqueConstraint(
            "loan_request_id",
            "company_id",
            name="uq_loan_offer_request_company",
        ),
    )

    loan_request_id = Column(
        UUID(as_uuid=True),
        ForeignKey("loan_requests.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    company_id = Column(
        UUID(as_uuid=True),
        ForeignKey("loan_companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    branch_id = Column(
        UUID(as_uuid=True),
        ForeignKey("company_branches.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    offered_by_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )

    approved_amount = Column(Numeric(12, 2), nullable=False)
    term_months = Column(Integer, nullable=False)
    interest_rate_percent = Column(Numeric(6, 3), nullable=False, default=0)
    processing_fee = Column(Numeric(12, 2), nullable=False, default=0)
    monthly_repayment = Column(Numeric(12, 2), nullable=False)
    total_repayment = Column(Numeric(12, 2), nullable=False)
    calculation_method = Column(Text, nullable=False, default="micro_loan")
    calculation_breakdown = Column(JSONB, nullable=False, default=dict)
    notes = Column(Text, nullable=True)

    status = Column(
        Enum(OfferStatus),
        nullable=False,
        default=OfferStatus.PENDING,
        index=True,
    )
    expires_at = Column(DateTime, nullable=True)
    accepted_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    loan_request = relationship(
        "LoanRequest",
        back_populates="offers",
        foreign_keys=[loan_request_id],
    )
    company = relationship("LoanCompany", back_populates="offers")
    branch = relationship("CompanyBranch")
    offered_by = relationship("User")
    loan = relationship(
        "ClientCompanyLoan",
        back_populates="loan_offer",
        uselist=False,
        foreign_keys="ClientCompanyLoan.loan_offer_id",
    )
