from sqlalchemy import Column, Enum, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from database.base import Base
from database.models.enums import PaymentDirection


class CashTransaction(Base):
    """Auditable cash-in or cash-out evidence linked to one payment transaction."""

    __tablename__ = "cash_transactions"
    __table_args__ = (
        UniqueConstraint("payment_id", name="uq_cash_transaction_payment"),
        UniqueConstraint("cash_reference", name="uq_cash_transaction_reference"),
    )

    payment_id = Column(
        UUID(as_uuid=True),
        ForeignKey("payment_transactions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    branch_id = Column(
        UUID(as_uuid=True),
        ForeignKey("company_branches.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    handled_by_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    direction = Column(Enum(PaymentDirection), nullable=False, index=True)
    cash_reference = Column(String(80), nullable=False, index=True)
    tendered_amount = Column(Numeric(15, 2), nullable=False, default=0)
    applied_amount = Column(Numeric(15, 2), nullable=False, default=0)
    change_amount = Column(Numeric(15, 2), nullable=False, default=0)
    forward_amount = Column(Numeric(15, 2), nullable=False, default=0)
    installment_number = Column(Integer, nullable=True)
    expected_installment_amount = Column(Numeric(15, 2), nullable=True)
    installment_outstanding_before = Column(Numeric(15, 2), nullable=True)
    installment_outstanding_after = Column(Numeric(15, 2), nullable=True)
    notes = Column(Text, nullable=True)

    payment = relationship("PaymentTransaction", back_populates="cash_transaction")
    branch = relationship("CompanyBranch")
    handled_by = relationship("User", foreign_keys=[handled_by_user_id])
