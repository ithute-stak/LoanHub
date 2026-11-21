"""PostgreSQL issuer connection and transaction identity checks."""
import os
from unittest.mock import Mock

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

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


def test_real_postgresql_new_transaction_fingerprint_is_rejected():
    url = os.getenv("LOANHUB_ISSUANCE_TEST_POSTGRES_URL")
    if not url:
        pytest.skip("Real PostgreSQL test URL required")
    engine = create_engine(url)
    try:
        with engine.connect() as conn:
            with conn.begin():
                with Session(bind=conn) as db:
                    original = read_issuer_transaction_identity(db=db)
                    require_same_issuer_transaction(db=db, expected=original)
            with conn.begin():
                with Session(bind=conn) as db:
                    current = read_issuer_transaction_identity(db=db)
                    assert current.backend_pid == original.backend_pid
                    assert current.transaction_id != original.transaction_id
                    with pytest.raises(PermissionError, match="transaction changed"):
                        require_same_issuer_transaction(db=db, expected=original)
    finally:
        engine.dispose()
