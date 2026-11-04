import base64
import os
from uuid import uuid4

import pytest
from cryptography.exceptions import InvalidTag

from services.signature_evidence_vault import (
    decrypt_signature_evidence,
    encrypt_signature_evidence,
    store_encrypted_signature_evidence,
)


def config():
    return dict(
        key_b64=base64.b64encode(os.urandom(32)).decode(),
        company_id=uuid4(), borrower_id=uuid4(), session_id=uuid4(),
        contract_hash="a" * 64,
    )


def test_signature_evidence_roundtrip_with_contract_bound_aad():
    args = config()
    raw = b'{"strokes":[[{"x":1,"y":2,"pressure":0.5}]]}'
    blob, digest = encrypt_signature_evidence(raw, **args)
    assert raw not in blob
    assert len(digest) == 64
    assert decrypt_signature_evidence(blob, **args) == raw
    for field, value in [
        ("company_id", uuid4()), ("borrower_id", uuid4()),
        ("session_id", uuid4()), ("contract_hash", "b" * 64),
    ]:
        altered = dict(args)
        altered[field] = value
        with pytest.raises(InvalidTag):
            decrypt_signature_evidence(blob, **altered)


def test_tamper_rejected():
    args = config()
    blob, _ = encrypt_signature_evidence(b"test signing pen points", **args)
    tampered = bytearray(blob)
    tampered[-1] ^= 1
    with pytest.raises(InvalidTag):
        decrypt_signature_evidence(bytes(tampered), **args)


@pytest.mark.parametrize("evidence", [b"", b"x" * 512_001])
def test_oversized_or_empty_rejected(evidence):
    with pytest.raises(ValueError):
        encrypt_signature_evidence(evidence, **config())


def test_bad_key_rejected():
    args = config()
    args["key_b64"] = base64.b64encode(b"short").decode()
    with pytest.raises(ValueError):
        encrypt_signature_evidence(b"data", **args)


def test_storage_receives_only_encrypted_bytes():
    class Storage:
        def put(self, key, content):
            self.key, self.content = key, content

    storage = Storage()
    args = config()
    evidence = b"unique-pen-evidence-that-must-not-be-plaintext"
    key, digest = store_encrypted_signature_evidence(storage, evidence, **args)
    assert key == storage.key
    assert key.startswith(f"signatures/v1/{args['company_id']}/{args['borrower_id']}/")
    assert storage.content.startswith(b"LHSV1")
    assert evidence not in storage.content
    assert decrypt_signature_evidence(storage.content, **args) == evidence
    assert len(digest) == 64
