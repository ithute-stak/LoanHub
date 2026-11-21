"""PostgreSQL issuer connection and transaction identity checks."""
from unittest.mock import Mock

import pytest

from services.document_issuance_transaction_guard import (
    IssuerTransactionIdentity, read_issuer_transaction_identity,
    require_same_issuer_transaction,
)


def _db(pid=12345, xid="987"):
    db = Mock()
    db.bind.dialect.name = "postgresql"
    db.execute.return_value.mappings.return_value.one.return_value = {
        "backend_pid": pid, "transaction_id": xid,
    }
    return db


def test_same_postgresql_transaction_accepted():
    db = _db()
    identity = read_issuer_transaction_identity(db=db)
    assert identity == IssuerTransactionIdentity(backend_pid=12345, transaction_id="987")
    require_same_issuer_transaction(db=db, expected=identity)


@pytest.mark.parametrize("pid,xid", [
    (12346, "987"), (12345, "988"),
])
def test_changed_backend_or_transaction_denied(pid, xid):
    db = _db(pid, xid)
    with pytest.raises(PermissionError, match="transaction changed"):
        require_same_issuer_transaction(
            db=db, expected=IssuerTransactionIdentity(backend_pid=12345, transaction_id="987"),
        )


@pytest.mark.parametrize("pid,xid", [
    (None, "987"), ("12345", "987"), (0, "987"),
    (12345, None), (12345, "not-a-transaction"), (12345, ""),
])
def test_unverifiable_identity_denied(pid, xid):
    with pytest.raises(PermissionError, match="Unverifiable"):
        read_issuer_transaction_identity(db=_db(pid, xid))


def test_non_postgresql_identity_denied():
    db = _db()
    db.bind.dialect.name = "sqlite"
    with pytest.raises(PermissionError, match="PostgreSQL"):
        read_issuer_transaction_identity(db=db)
