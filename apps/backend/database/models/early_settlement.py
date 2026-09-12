from sqlalchemy import Boolean, CheckConstraint, Column, Date, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from database.base import Base


class LoanEarlySettlement(Base):
    """Immutable quote/snapshot plus the eventual early-payoff lifecycle."""

    __tablename__ = "loan_early_settlements"
    __table_args__ = (
        CheckConstraint(
            "status IN ('quoted','processing','settled','failed','expired','reversed')",
            name="ck_early_settlement_status",
        ),
        Index(
            "uq_early_settlement_open_loan",
            "loan_id",
            unique=True,
            postgresql_where=text("status IN ('quoted','processing')"),
        ),
    )

    company_id = Column(
        UUID(as_uuid=True),
        ForeignKey("loan_companies.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    borrower_id = Column(
        UUID(as_uuid=True),
        ForeignKey("borrowers.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    loan_id = Column(
        UUID(as_uuid=True),
        ForeignKey("client_company_loan.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    payment_id = Column(
        UUID(as_uuid=True),
        ForeignKey("payment_transactions.id", ondelete="SET NULL"),
        nullable=True,
        unique=True,
        index=True,
    )
    quoted_by_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    settled_by_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    status = Column(String(24), nullable=False, default="quoted", index=True)
    settlement_date = Column(Date, nullable=False, index=True)
    quote_expires_at = Column(DateTime, nullable=False, index=True)
    calculation_method = Column(String(40), nullable=False)
    original_term_months = Column(Integer, nullable=False)
    chargeable_periods = Column(Integer, nullable=False)
    original_maturity_date = Column(Date, nullable=True)

    original_principal = Column(Numeric(15, 2), nullable=False)
    original_total_repayable = Column(Numeric(15, 2), nullable=False)
    original_balance = Column(Numeric(15, 2), nullable=False)
    original_amount_paid = Column(Numeric(15, 2), nullable=False)
    original_total_interest = Column(Numeric(15, 2), nullable=False)
    earned_interest = Column(Numeric(15, 2), nullable=False)
    unearned_interest_rebate = Column(Numeric(15, 2), nullable=False)
    processing_fee_retained = Column(Numeric(15, 2), nullable=False)
    payments_received = Column(Numeric(15, 2), nullable=False)
    revised_total_repayable = Column(Numeric(15, 2), nullable=False)
    settlement_amount = Column(Numeric(15, 2), nullable=False)
    settlement_principal = Column(Numeric(15, 2), nullable=False)
    settlement_interest = Column(Numeric(15, 2), nullable=False)
    settlement_fees = Column(Numeric(15, 2), nullable=False)
    overpayment_credit = Column(Numeric(15, 2), nullable=False, default=0)

    borrower_acknowledged = Column(Boolean, nullable=False, default=False)
    agreement_note = Column(Text, nullable=True)
    agreement_reference = Column(String(160), nullable=True)
    calculation_snapshot = Column(JSONB, nullable=False, default=dict)
    installment_snapshot = Column(JSONB, nullable=False, default=list)

    settled_at = Column(DateTime, nullable=True)
    reversed_at = Column(DateTime, nullable=True)

    loan = relationship("ClientCompanyLoan")
    payment = relationship("PaymentTransaction", foreign_keys=[payment_id])
