from sqlalchemy import Column, DateTime, Enum, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from database.base import Base
from database.models.enums import (
    PaymentDirection,
    PaymentMethod,
    PaymentProvider,
    PaymentPurpose,
    PaymentStatus,
)


class PaymentTransaction(Base):
    __tablename__ = "payment_transactions"

    company_id = Column(
        UUID(as_uuid=True),
        ForeignKey("loan_companies.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    borrower_id = Column(
        UUID(as_uuid=True),
        ForeignKey("borrowers.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    loan_request_id = Column(
        UUID(as_uuid=True),
        ForeignKey("loan_requests.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    loan_id = Column(
        UUID(as_uuid=True),
        ForeignKey("client_company_loan.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    direct_application_id = Column(
        UUID(as_uuid=True),
        ForeignKey("direct_loan_applications.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    company_borrower_account_id = Column(
        UUID(as_uuid=True),
        ForeignKey("company_borrower_accounts.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    initiated_by_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    provider = Column(Enum(PaymentProvider), nullable=False)
    payment_method = Column(
        Enum(PaymentMethod, native_enum=False, length=40, values_callable=lambda enum_cls: [item.value for item in enum_cls]),
        nullable=False,
        default=PaymentMethod.CASH,
        index=True,
    )
    direction = Column(Enum(PaymentDirection), nullable=False)
    purpose = Column(Enum(PaymentPurpose), nullable=False)
    status = Column(
        Enum(PaymentStatus),
        nullable=False,
        default=PaymentStatus.PENDING,
    )

    amount = Column(Numeric(15, 2), nullable=False)
    currency = Column(String(3), nullable=False, default="LSL")
    payer_phone = Column(String(30), nullable=True)
    payee_phone = Column(String(30), nullable=True)
    configuration_scope = Column(String(20), nullable=True)
    provider_operation = Column(String(60), nullable=True)

    idempotency_key = Column(String(255), nullable=False, unique=True, index=True)
    provider_reference = Column(String(180), nullable=True, unique=True, index=True)
    proof_reference = Column(String(180), nullable=True, index=True)
    proof_url = Column(String(500), nullable=True)
    proof_notes = Column(Text, nullable=True)
    verified_by_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    verified_at = Column(DateTime, nullable=True)
    provider_payload = Column(JSONB, nullable=False, default=dict)
    failure_reason = Column(Text, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    company = relationship("LoanCompany", back_populates="payment_transactions")
    borrower = relationship("Borrower", back_populates="payment_transactions")
    loan_request = relationship(
        "LoanRequest",
        back_populates="payment_transactions",
        foreign_keys=[loan_request_id],
    )
    loan = relationship("ClientCompanyLoan", back_populates="payment_transactions")
    company_borrower_account = relationship(
        "CompanyBorrowerAccount",
        foreign_keys=[company_borrower_account_id],
    )
    initiated_by = relationship(
        "User",
        foreign_keys=[initiated_by_user_id],
    )
    verified_by = relationship(
        "User",
        foreign_keys=[verified_by_user_id],
    )
    cash_transaction = relationship(
        "CashTransaction",
        back_populates="payment",
        uselist=False,
        cascade="all, delete-orphan",
    )
    unlock = relationship(
        "MarketplaceUnlock",
        back_populates="payment_transaction",
        uselist=False,
    )
    allocations = relationship(
        "PaymentAllocation",
        back_populates="payment",
        cascade="all, delete-orphan",
    )
