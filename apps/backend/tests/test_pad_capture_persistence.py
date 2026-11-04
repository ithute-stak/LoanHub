"""Internal capture service is fail closed and never marks LoanContract signed."""
import base64
import os
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from services.pad_capture_persistence import persist_verified_candidate_capture
from services.signature_evidence_vault import decrypt_signature_evidence


class Query:
    def __init__(self, row):
        self.row = row
        self.locked = False
    def filter(self, *conditions):
        return self
    def with_for_update(self, **kwargs):
        self.locked = True
        return self
    def one_or_none(self):
        return self.row


class Db:
    def __init__(self, contract, session, fail_commit=False):
        self.contract_query = Query(contract)
        self.session_query = Query(session)
        self.added = []
        self.commits = 0
        self.rollbacks = 0
        self.fail_commit = fail_commit
    def query(self, model):
        from database.models.origination import LoanContract
        return self.contract_query if model is LoanContract else self.session_query
    def add(self, record):
        self.added.append(record)
    def commit(self):
        if self.fail_commit:
            raise RuntimeError("db failed")
        self.commits += 1
    def rollback(self):
        self.rollbacks += 1


class Storage:
    def __init__(self):
        self.objects = {}
        self.deleted = []
    def put(self, key, data):
        self.objects[key] = data
    def delete(self, key):
        self.deleted.append(key)
        self.objects.pop(key, None)


def setup():
    now = datetime.now(timezone.utc)
    company, borrower, contract_id, session_id, operator = [uuid4() for _ in range(5)]
    contract = SimpleNamespace(
        id=contract_id, company_id=company, borrower_id=borrower,
        contract_hash="a" * 64, pdf_file_id=uuid4(),
        borrower_signed_at=None, locked_at=None, status="draft",
    )
    session = SimpleNamespace(
        id=session_id, company_id=company, contract_id=contract_id,
        operator_user_id=operator, expires_at=now+timedelta(minutes=5),
        status="consented", verified_identity_at=now-timedelta(minutes=2),
        consent_at=now-timedelta(minutes=1), consent_version="v1",
        evidence_sha256=None, evidence=None,
    )
    db, storage = Db(contract, session), Storage()
    args = dict(
        db=db, storage=storage,
        encryption_key_b64=base64.b64encode(os.urandom(32)).decode(),
        company_id=company, borrower_id=borrower, contract_id=contract_id,
        session_id=session_id, operator_id=operator,
        strokes=[[{"x":1.0, "y":2.0, "at":1000, "pressure":0.5},
                  {"x":3.0, "y":4.0, "at":1005, "pressure":0.3}]],
        capture_provenance_verified=True, now=now,
    )
    return args, contract, session


def test_persist_encrypts_and_does_not_sign_contract():
    args, contract, session = setup()
    result = persist_verified_candidate_capture(**args)
    assert result["contract_signed"] is False
    assert result["status"] == "captured"
    assert contract.borrower_signed_at is None
    assert contract.status == "draft"
    assert session.status == "captured"
    assert len(args["storage"].objects) == 1
    assert args["db"].contract_query.locked and args["db"].session_query.locked
    assert args["db"].commits == 1
    key, ciphertext = next(iter(args["storage"].objects.items()))
    assert b'"strokes"' not in ciphertext
    plaintext = decrypt_signature_evidence(
        ciphertext, key_b64=args["encryption_key_b64"],
        company_id=args["company_id"], borrower_id=args["borrower_id"],
        session_id=args["session_id"], contract_hash=contract.contract_hash,
    )
    assert b'"strokes"' in plaintext
    assert args["db"].added[0].encrypted_storage_key == key


@pytest.mark.parametrize("case,status", [
    ("untrusted", 403), ("unconsented", 409), ("expired", 409),
    ("wrong_contract_hash", 409), ("existing_evidence", 409),
    ("already_signed", 409),
])
def test_rejects_invalid_capture_state_without_writing(case, status):
    args, contract, session = setup()
    if case == "untrusted":
        args["capture_provenance_verified"] = False
    elif case == "unconsented":
        session.consent_at = None
    elif case == "expired":
        session.expires_at = args["now"]
    elif case == "wrong_contract_hash":
        contract.contract_hash = "b" * 64
    elif case == "existing_evidence":
        session.evidence_sha256 = "b" * 64
    elif case == "already_signed":
        contract.borrower_signed_at = args["now"]
    with pytest.raises(HTTPException) as error:
        persist_verified_candidate_capture(**args)
    assert error.value.status_code == status
    assert args["storage"].objects == {}
    assert args["db"].commits == 0


def test_database_failure_cleans_ciphertext():
    args, contract, session = setup()
    args["db"].fail_commit = True
    with pytest.raises(RuntimeError, match="db failed"):
        persist_verified_candidate_capture(**args)
    assert args["storage"].objects == {}
    assert len(args["storage"].deleted) == 1
    assert args["db"].rollbacks == 1
    assert contract.borrower_signed_at is None
