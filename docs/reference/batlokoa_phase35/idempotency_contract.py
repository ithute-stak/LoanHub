"""Future-only classification; requires approved durable PostgreSQL reservation."""
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum

class KeyDecision(str, Enum):
    NEW = "new"
    REPEAT = "repeat"
    CONFLICT = "conflict"

@dataclass(frozen=True)
class StoredReservation:
    company_id: str
    idempotency_key: str
    fingerprint: str

def classify_reused_key(*, company_id: str, idempotency_key: str,
                        fingerprint: str, stored: StoredReservation | None) -> KeyDecision:
    if stored is None:
        return KeyDecision.NEW
    if stored.company_id != company_id or stored.idempotency_key != idempotency_key:
        raise ValueError("Reservation lookup returned wrong company/key")
    if stored.fingerprint == fingerprint:
        return KeyDecision.REPEAT
    return KeyDecision.CONFLICT
