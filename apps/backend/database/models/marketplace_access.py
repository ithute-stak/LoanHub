from sqlalchemy import Column, DateTime, Enum, ForeignKey, Numeric, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from database.base import Base
from database.models.enums import UnlockStatus


class MarketplaceUnlock(Base):
    __tablename__ = "marketplace_unlocks"
    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "loan_request_id",
            name="uq_marketplace_unlock_company_request",
        ),
    )

    company_id = Column(
        UUID(as_uuid=True),
        ForeignKey("loan_companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    loan_request_id = Column(
        UUID(as_uuid=True),
        ForeignKey("loan_requests.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    payment_transaction_id = Column(
        UUID(as_uuid=True),
        ForeignKey("payment_transactions.id", ondelete="SET NULL"),
        nullable=True,
        unique=True,
    )
    unlocked_by_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    price_paid = Column(Numeric(12, 2), nullable=False, default=0)
    status = Column(Enum(UnlockStatus), nullable=False, default=UnlockStatus.PENDING)
    unlocked_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True)

    company = relationship("LoanCompany", back_populates="marketplace_unlocks")
    loan_request = relationship("LoanRequest", back_populates="marketplace_unlocks")
    payment_transaction = relationship("PaymentTransaction", back_populates="unlock")
    unlocked_by = relationship("User")
