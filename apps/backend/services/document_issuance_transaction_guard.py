"""Experimental PostgreSQL transaction identity check for official issuance.

A SQLAlchemy Session root transaction object alone cannot prove that the
underlying PostgreSQL transaction/connection did not change. The transaction
fingerprint is sampled after acquiring issuer locks and compared immediately
before SQL COMMIT. It does not replace a trusted issuer or verify human identity.
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.orm import Session


@dataclass(frozen=True)
class IssuerTransactionIdentity:
    backend_pid: int
    transaction_id: str


def read_issuer_transaction_identity(*, db: Session) -> IssuerTransactionIdentity:
    """Get an actual PostgreSQL transaction identifier, failing closed."""
    if db.bind is None or db.bind.dialect.name != "postgresql":
        raise PermissionError("PostgreSQL issuer transaction required")
    row = db.execute(text("""
        SELECT pg_backend_pid() AS backend_pid,
               pg_current_xact_id()::text AS transaction_id
    """)).mappings().one()
    pid, xid = row["backend_pid"], row["transaction_id"]
    if type(pid) is not int or pid <= 0 or not isinstance(xid, str) or not xid.isdigit():
        raise PermissionError("Unverifiable PostgreSQL issuer transaction")
    return IssuerTransactionIdentity(backend_pid=pid, transaction_id=xid)


def require_same_issuer_transaction(
    *, db: Session, expected: IssuerTransactionIdentity,
) -> None:
    if read_issuer_transaction_identity(db=db) != expected:
        raise PermissionError("PostgreSQL issuer transaction changed before commit")
