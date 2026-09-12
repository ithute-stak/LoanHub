from sqlalchemy import Boolean, Column, Date, DateTime, Enum, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from database.base import Base
from database.models.enums import LoanStatus, RepaymentType, RiskLevel


class ClientCompanyLoan(Base):
    __tablename__ = "client_company_loan"
    __table_args__ = (
        UniqueConstraint("loan_request_id", name="uq_client_loan_request"),
        UniqueConstraint("loan_offer_id", name="uq_client_loan_offer"),
    )

    loan_request_id = Column(
        UUID(as_uuid=True),
        ForeignKey("loan_requests.id", ondelete="RESTRICT"),
        nullable=True,
    )
    loan_offer_id = Column(
        UUID(as_uuid=True),
        ForeignKey("loan_offers.id", ondelete="RESTRICT"),
        nullable=True,
    )

    company_id = Column(
        UUID(as_uuid=True),
        ForeignKey("loan_companies.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    branch_id = Column(
        UUID(as_uuid=True),
        ForeignKey("company_branches.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    borrower_id = Column(
        UUID(as_uuid=True),
        ForeignKey("borrowers.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    loan_reference = Column(String(100), unique=True, nullable=False, index=True)
    origination_channel = Column(String(30), nullable=False, default="marketplace", index=True)
    direct_application_id = Column(UUID(as_uuid=True), ForeignKey("direct_loan_applications.id", ondelete="SET NULL"), nullable=True, unique=True)
    is_top_up = Column(Boolean, nullable=False, default=False, index=True)
    parent_loan_id = Column(UUID(as_uuid=True), ForeignKey("client_company_loan.id", ondelete="SET NULL"), nullable=True, index=True)
    top_up_settlement_amount = Column(Numeric(15, 2), nullable=False, default=0)
    top_up_cash_amount = Column(Numeric(15, 2), nullable=False, default=0)
    principal_amount = Column(Numeric(15, 2), nullable=False)
    interest_rate = Column(Numeric(6, 3), nullable=False, default=0)
    processing_fee = Column(Numeric(15, 2), nullable=False, default=0)
    total_repayable = Column(Numeric(15, 2), nullable=False)

    repayment_type = Column(Enum(RepaymentType), nullable=False, default=RepaymentType.MONTHLY)
    repayment_period = Column(Integer, nullable=False)
    installment_amount = Column(Numeric(15, 2), nullable=False)
    calculation_method = Column(String(40), nullable=False, default="micro_loan")
    calculation_breakdown = Column(JSONB, nullable=False, default=dict)

    approved_at = Column(DateTime, nullable=True)
    disbursed_at = Column(DateTime, nullable=True)
    first_payment_due = Column(Date, nullable=True)
    preferred_payment_day = Column(Integer, nullable=True)
    maturity_date = Column(Date, nullable=True)

    amount_paid = Column(Numeric(15, 2), nullable=False, default=0)
    balance = Column(Numeric(15, 2), nullable=False)

    status = Column(Enum(LoanStatus), nullable=False, default=LoanStatus.PENDING)
    risk_level = Column(Enum(RiskLevel), nullable=False, default=RiskLevel.LOW)
    is_overdue = Column(Boolean, nullable=False, default=False)

    # Maturity-renewal control. ``None`` inherits the company policy; explicit
    # True/False is a facility-level override. Renewals never create a fake
    # disbursement and remain attached to this master loan.
    automatic_renewal_enabled = Column(Boolean, nullable=True)
    renewal_cycle_count = Column(Integer, nullable=False, default=0)
    original_maturity_date = Column(Date, nullable=True)
    last_renewed_at = Column(DateTime, nullable=True)
    renewal_stopped_at = Column(DateTime, nullable=True)
    renewal_stopped_by_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    renewal_stop_reason = Column(Text, nullable=True)

    approved_by_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    disbursed_by_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    borrower = relationship("Borrower", back_populates="loans")
    company = relationship("LoanCompany", back_populates="loans")
    branch = relationship("CompanyBranch", back_populates="loans")
    loan_request = relationship("LoanRequest", back_populates="loan", foreign_keys=[loan_request_id])
    loan_offer = relationship("LoanOffer", back_populates="loan", foreign_keys=[loan_offer_id])
    approved_by = relationship("User", foreign_keys=[approved_by_user_id])
    disbursed_by = relationship("User", foreign_keys=[disbursed_by_user_id])
    installments = relationship(
        "RepaymentInstallment",
        back_populates="loan",
        cascade="all, delete-orphan",
        order_by="RepaymentInstallment.installment_number",
    )
    payment_transactions = relationship("PaymentTransaction", back_populates="loan")
    parent_loan = relationship("ClientCompanyLoan", remote_side="ClientCompanyLoan.id", foreign_keys=[parent_loan_id])
    renewal_cycles = relationship(
        "LoanRenewalCycle",
        back_populates="loan",
        cascade="all, delete-orphan",
        order_by="LoanRenewalCycle.cycle_number",
    )
