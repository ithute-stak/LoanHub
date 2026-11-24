"""Atomic reservation writer for Principal x collection posting.

Must be called in the SAME PostgreSQL transaction as loan row locking,
authoritative reconciliation and payment creation. No commit here.
"""
from uuid import UUID

from sqlalchemy.orm import Session

from database.models.principal_x_collection_reservation import PrincipalXCollectionReservation
from payment_engine.principal_x_collection_ceiling import money


def reserve_principal_x_collection(
    db: Session, *, company_id: UUID, loan_id: UUID,
    amount, idempotency_key: str, provider_reference: str,
) -> PrincipalXCollectionReservation:
    if db.get_bind().dialect.name != "postgresql":
        raise ValueError("PostgreSQL required for durable reservation")
    if not isinstance(company_id, UUID) or not isinstance(loan_id, UUID):
        raise ValueError("Company and loan UUIDs required")
    if not isinstance(idempotency_key, str) or not idempotency_key.strip():
        raise ValueError("Idempotency key required")
    if not isinstance(provider_reference, str) or not provider_reference.strip():
        raise ValueError("Provider reference required")
    if len(idempotency_key) > 255 or len(provider_reference) > 180:
        raise ValueError("Payment reference exceeds database column length")
    value = money(amount)
    if value <= 0:
        raise ValueError("Reservation amount must be positive")
    row = PrincipalXCollectionReservation(
        company_id=company_id, loan_id=loan_id,
        amount=value, idempotency_key=idempotency_key,
        provider_reference=provider_reference,
    )
    db.add(row)
    # Flush invokes PostgreSQL unique constraints before further processing.
    # IntegrityError is intentionally NOT swallowed; caller rolls back.
    db.flush()
    return row


def bind_principal_x_payment(
    db: Session, *, reservation: PrincipalXCollectionReservation,
    payment_transaction_id: UUID,
) -> None:
    if not isinstance(payment_transaction_id, UUID):
        raise ValueError("Payment transaction UUID required")
    if reservation.payment_transaction_id is not None:
        raise ValueError("Reservation already bound to a payment")
    reservation.payment_transaction_id = payment_transaction_id
    db.flush()
