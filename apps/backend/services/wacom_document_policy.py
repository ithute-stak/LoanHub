"""Pure domain policy for first-party Wacom document-signing intents.

No image, saved signature or workstation session is itself a contract signature.
Document hash, actor identity and explicit per-document signer consent are bound
into a single digest; no network, DB or clock access in the policy functions.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from uuid import UUID

HEX64 = re.compile(r"^[0-9a-f]{64}$")


class IntentStatus(str, Enum):
    PREPARED = "prepared"
    CONSENTED = "consented"
    EVIDENCE_UPLOADED = "evidence_uploaded"
    VERIFIED = "verified"
    REJECTED = "rejected"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class IntentIdentity:
    company_id: UUID
    borrower_id: UUID
    contract_id: UUID
    source_file_id: UUID
    operator_user_id: UUID
    workstation_id: UUID
    document_sha256: str
    document_version: str

    def __post_init__(self):
        if not HEX64.fullmatch(self.document_sha256):
            raise ValueError("A canonical SHA-256 of the exact document bytes is required")
        if not self.document_version or len(self.document_version) > 80:
            raise ValueError("A bounded exact document version identifier is required")

    def canonical(self) -> bytes:
        return json.dumps({
            "domain": "LOANHUB-WACOM-DOCUMENT-V1",
            "borrower_id": str(self.borrower_id),
            "company_id": str(self.company_id),
            "contract_id": str(self.contract_id),
            "source_file_id": str(self.source_file_id),
            "document_sha256": self.document_sha256,
            "document_version": self.document_version,
            "operator_user_id": str(self.operator_user_id),
            "workstation_id": str(self.workstation_id),
        }, separators=(",", ":"), sort_keys=True, ensure_ascii=True).encode("ascii")

    def binding_sha256(self) -> str:
        return hashlib.sha256(self.canonical()).hexdigest()


def verify_document_bytes(expected_sha256: str, payload: bytes) -> None:
    if not HEX64.fullmatch(expected_sha256):
        raise ValueError("invalid document hash")
    if not payload or hashlib.sha256(payload).hexdigest() != expected_sha256:
        raise ValueError("document changed after signer consent")


def require_transition(status: str, target: str) -> None:
    graph = {
        IntentStatus.PREPARED: {IntentStatus.CONSENTED, IntentStatus.CANCELLED, IntentStatus.EXPIRED},
        IntentStatus.CONSENTED: {IntentStatus.EVIDENCE_UPLOADED, IntentStatus.CANCELLED, IntentStatus.EXPIRED},
        IntentStatus.EVIDENCE_UPLOADED: {IntentStatus.VERIFIED, IntentStatus.REJECTED, IntentStatus.CANCELLED},
        IntentStatus.VERIFIED: set(),
        IntentStatus.REJECTED: set(),
        IntentStatus.CANCELLED: set(),
        IntentStatus.EXPIRED: set(),
    }
    if target not in graph.get(status, set()):
        raise ValueError(f"forbidden Wacom intent state transition: {status} -> {target}")


def check_valid_until(deadline: datetime, *, now: datetime | None = None) -> None:
    now = now or datetime.now(timezone.utc)
    if deadline.tzinfo is None or now.tzinfo is None or now >= deadline:
        raise ValueError("document-specific consent window expired")


def consent_digest(binding_sha256: str, signer_confirmation: str, consent_reference: str) -> str:
    """Audit commitment, not proof of signer identity or legal consent by itself."""
    if not HEX64.fullmatch(binding_sha256):
        raise ValueError("invalid document binding")
    if signer_confirmation != "I agree to sign this exact document":
        raise ValueError("explicit per-document consent confirmation required")
    if not 4 <= len(consent_reference.strip()) <= 180:
        raise ValueError("consent evidence reference required")
    encoded = "\n".join(("LOANHUB-WACOM-CONSENT-V1", binding_sha256, consent_reference.strip())).encode()
    return hashlib.sha256(encoded).hexdigest()
