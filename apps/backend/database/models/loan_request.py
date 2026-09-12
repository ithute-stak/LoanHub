from sqlalchemy import Boolean, Column, DateTime, Enum, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from database.base import Base
from database.models.enums import LoanRequestStatus


class LoanRequest(Base):
    __tablename__ = "loan_requests"

    borrower_id = Column(
        UUID(as_uuid=True),
        ForeignKey("borrowers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    requested_amount = Column(Numeric(12, 2), nullable=False)
    preferred_term_months = Column(Integer, nullable=True)
    loan_purpose = Column(Text, nullable=True)

    status = Column(
        Enum(LoanRequestStatus),
        nullable=False,
        default=LoanRequestStatus.DRAFT,
        index=True,
    )
    visible_to_lenders = Column(Boolean, nullable=False, default=False)
    allow_lenders_to_call = Column(Boolean, nullable=False, default=True)

    origination_channel = Column(String(30), nullable=False, default="online")
    captured_by_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    service_fee_amount = Column(Numeric(15, 2), nullable=False, default=0)
    service_fee_currency = Column(String(3), nullable=False, default="LSL")
    service_fee_status = Column(String(30), nullable=False, default="not_required", index=True)
    service_fee_payment_id = Column(
        UUID(as_uuid=True),
        ForeignKey("payment_transactions.id", ondelete="SET NULL", use_alter=True),
        nullable=True,
        unique=True,
    )

    selected_offer_id = Column(
        UUID(as_uuid=True),
        ForeignKey(
            "loan_offers.id",
            name="loan_requests_selected_offer_id_fkey",
            ondelete="SET NULL",
            use_alter=True,
        ),
        nullable=True,
        unique=True,
    )

    submitted_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True, index=True)
    accepted_at = Column(DateTime, nullable=True)

    # Kept explicitly because older migrations created it on this model.
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    borrower = relationship("Borrower", back_populates="loan_requests")
    offers = relationship(
        "LoanOffer",
        back_populates="loan_request",
        cascade="all, delete-orphan",
        foreign_keys="LoanOffer.loan_request_id",
    )
    selected_offer = relationship(
        "LoanOffer",
        foreign_keys=[selected_offer_id],
        post_update=True,
    )
    documents = relationship(
        "LoanRequestDocument",
        back_populates="loan_request",
        cascade="all, delete-orphan",
    )
    access_requests = relationship(
        "LenderAccessRequest",
        back_populates="loan_request",
        cascade="all, delete-orphan",
    )
    marketplace_unlocks = relationship(
        "MarketplaceUnlock",
        back_populates="loan_request",
        cascade="all, delete-orphan",
    )
    payment_transactions = relationship(
        "PaymentTransaction",
        back_populates="loan_request",
        foreign_keys="PaymentTransaction.loan_request_id",
    )
    service_fee_payment = relationship(
        "PaymentTransaction",
        foreign_keys=[service_fee_payment_id],
        post_update=True,
    )
    loan = relationship(
        "ClientCompanyLoan",
        back_populates="loan_request",
        uselist=False,
        foreign_keys="ClientCompanyLoan.loan_request_id",
    )
