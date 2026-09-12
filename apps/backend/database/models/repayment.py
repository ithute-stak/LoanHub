from sqlalchemy import Boolean, Column, Date, DateTime, Enum, ForeignKey, Integer, Numeric, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from database.base import Base
from database.models.enums import InstallmentStatus


class RepaymentInstallment(Base):
    __tablename__ = "repayment_installments"
    __table_args__ = (
        UniqueConstraint(
            "loan_id",
            "installment_number",
            name="uq_repayment_installment_loan_number",
        ),
    )

    loan_id = Column(
        UUID(as_uuid=True),
        ForeignKey("client_company_loan.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    renewal_cycle_id = Column(
        UUID(as_uuid=True),
        ForeignKey("loan_renewal_cycles.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    superseded_by_cycle_id = Column(
        UUID(as_uuid=True),
        ForeignKey("loan_renewal_cycles.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    is_superseded = Column(Boolean, nullable=False, default=False, index=True)
    superseded_at = Column(DateTime, nullable=True)
    installment_number = Column(Integer, nullable=False)
    due_date = Column(Date, nullable=False, index=True)

    principal_due = Column(Numeric(15, 2), nullable=False, default=0)
    interest_due = Column(Numeric(15, 2), nullable=False, default=0)
    fee_due = Column(Numeric(15, 2), nullable=False, default=0)
    total_due = Column(Numeric(15, 2), nullable=False)
    paid_amount = Column(Numeric(15, 2), nullable=False, default=0)

    status = Column(
        Enum(InstallmentStatus),
        nullable=False,
        default=InstallmentStatus.PENDING,
    )
    paid_at = Column(DateTime, nullable=True)

    loan = relationship("ClientCompanyLoan", back_populates="installments")
    allocations = relationship(
        "PaymentAllocation",
        back_populates="installment",
        cascade="all, delete-orphan",
    )


class PaymentAllocation(Base):
    __tablename__ = "payment_allocations"
    __table_args__ = (
        UniqueConstraint(
            "payment_id",
            "installment_id",
            name="uq_payment_allocation_payment_installment",
        ),
    )

    payment_id = Column(
        UUID(as_uuid=True),
        ForeignKey("payment_transactions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    installment_id = Column(
        UUID(as_uuid=True),
        ForeignKey("repayment_installments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    amount = Column(Numeric(15, 2), nullable=False)

    payment = relationship("PaymentTransaction", back_populates="allocations")
    installment = relationship("RepaymentInstallment", back_populates="allocations")
