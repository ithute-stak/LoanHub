"""Authenticated encryption for candidate signature evidence in object storage.

Not a contract-signing endpoint. Caller must enforce identity, consent,
tenant/borrower access and session state before using these primitives.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
from uuid import UUID, uuid4

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

MAX_EVIDENCE_BYTES = 512_000


def _key_from_b64(encoded_key: str) -> bytes:
    if not encoded_key:
        raise ValueError("Dedicated signature evidence encryption key is required")
    try:
        key = base64.b64decode(encoded_key, validate=True)
    except (ValueError, base64.binascii.Error) as error:
        raise ValueError("Signature evidence key is invalid base64") from error
    if len(key) != 32:
        raise ValueError("Signature evidence encryption key must be 256 bits")
    return key


def _aad(*, company_id: UUID, borrower_id: UUID, session_id: UUID, contract_hash: str) -> bytes:
    if len(contract_hash) != 64 or any(char not in "0123456789abcdef" for char in contract_hash):
        raise ValueError("Invalid contract hash")
    return json.dumps({
        "borrower_id": str(borrower_id),
        "company_id": str(company_id),
        "contract_hash": contract_hash,
        "session_id": str(session_id),
        "version": 1,
    }, sort_keys=True, separators=(",", ":")).encode()


def encrypt_signature_evidence(
    evidence: bytes, *, key_b64: str,
    company_id: UUID, borrower_id: UUID, session_id: UUID, contract_hash: str,
) -> tuple[bytes, str]:
    if not isinstance(evidence, bytes) or not 1 <= len(evidence) <= MAX_EVIDENCE_BYTES:
        raise ValueError("Invalid signature evidence size")
    key = _key_from_b64(key_b64)
    aad = _aad(company_id=company_id, borrower_id=borrower_id, session_id=session_id, contract_hash=contract_hash)
    nonce = os.urandom(12)
    ciphertext = AESGCM(key).encrypt(nonce, evidence, aad)
    # Magic + nonce + authenticated ciphertext; never include plaintext in object storage.
    blob = b"LHSV1" + nonce + ciphertext
    return blob, hashlib.sha256(evidence).hexdigest()


def decrypt_signature_evidence(
    blob: bytes, *, key_b64: str,
    company_id: UUID, borrower_id: UUID, session_id: UUID, contract_hash: str,
) -> bytes:
    if not isinstance(blob, bytes) or not blob.startswith(b"LHSV1") or len(blob) < 5 + 12 + 16:
        raise ValueError("Invalid signature evidence envelope")
    key = _key_from_b64(key_b64)
    aad = _aad(company_id=company_id, borrower_id=borrower_id, session_id=session_id, contract_hash=contract_hash)
    return AESGCM(key).decrypt(blob[17:29], blob[29:], aad)


def store_encrypted_signature_evidence(
    storage, evidence: bytes, *, key_b64: str,
    company_id: UUID, borrower_id: UUID, session_id: UUID, contract_hash: str,
) -> tuple[str, str]:
    """Write encrypted bytes only; caller transaction persists key and digest."""
    blob, digest = encrypt_signature_evidence(
        evidence, key_b64=key_b64, company_id=company_id,
        borrower_id=borrower_id, session_id=session_id, contract_hash=contract_hash,
    )
    object_key = f"signatures/v1/{company_id}/{borrower_id}/{session_id}/{uuid4().hex}.enc"
    storage.put(object_key, blob)
    return object_key, digest
