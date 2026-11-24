"""Durable, loan-owned Principal x collection reservation.

Uniqueness is enforced by PostgreSQL, not by a pre-insert SELECT. The
reservation and payment must be persisted within the same transaction.
"""
from sqlalchemy import CheckConstraint, Column, ForeignKey, ForeignKeyConstraint, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID

from database.base import Base


class PrincipalXCollectionReservation(Base):
    __tablename__ = "principal_x_collection_reservations"
    __table_args__ = (
        ForeignKeyConstraint(
            ["loan_id", "company_id"],
            ["client_company_loan.id", "client_company_loan.company_id"],
            name="fk_principal_x_reservation_loan_owner",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("idempotency_key", name="uq_principal_x_reservation_idempotency"),
        UniqueConstraint("provider_reference", name="uq_principal_x_reservation_provider_reference"),
        UniqueConstraint("payment_transaction_id", name="uq_principal_x_reservation_payment"),
        CheckConstraint("amount > 0", name="ck_principal_x_reservation_positive"),
        CheckConstraint("length(trim(idempotency_key)) > 0", name="ck_principal_x_reservation_key_nonempty"),
        CheckConstraint("length(trim(provider_reference)) > 0", name="ck_principal_x_reservation_provider_nonempty"),
    )

    company_id = Column(UUID(as_uuid=True), nullable=False)
    loan_id = Column(UUID(as_uuid=True), nullable=False)
    idempotency_key = Column(String(255), nullable=False)
    provider_reference = Column(String(180), nullable=False)
    amount = Column(Numeric(15, 2), nullable=False)
    payment_transaction_id = Column(
        UUID(as_uuid=True),
        ForeignKey("payment_transactions.id", ondelete="RESTRICT"),
        nullable=True,
    )
