"""Pure Phase 38 append-only event and outbox proposals, never persisted here."""
from __future__ import annotations
from dataclasses import dataclass
from hashlib import sha256
import hmac, json
from uuid import UUID
from .contracts import TenantKey, ContractError, fingerprint, reference

@dataclass(frozen=True, slots=True)
class Event:
    tenant: TenantKey
    operation_id: str
    event_id: UUID
    version: int
    kind: str
    payload_digest: str
    previous_digest: str | None

    def __post_init__(self):
        reference(self.operation_id)
        fingerprint(self.payload_digest)
        if type(self.version) is not int or self.version < 1 or not isinstance(self.event_id, UUID):
            raise ContractError('Invalid event version or ID')
        if self.previous_digest is not None:
            fingerprint(self.previous_digest)
        if self.version == 1 and self.previous_digest is not None:
            raise ContractError('Genesis event must have empty previous digest')
        if self.version > 1 and self.previous_digest is None:
            raise ContractError('Missing previous digest')
        if self.kind not in {'created', 'mandate_verified', 'submitted', 'unknown', 'failed', 'settled', 'reversal_requested', 'reversed'}:
            raise ContractError('Unsupported event kind')

def digest(event: Event) -> str:
    body = dict(version=event.version, event_id=str(event.event_id),
                company_id=str(event.tenant.company_id), loan_id=str(event.tenant.loan_id),
                borrower_id=str(event.tenant.borrower_id), operation_id=event.operation_id,
                kind=event.kind, payload_digest=event.payload_digest,
                previous_digest=event.previous_digest)
    return sha256(json.dumps(body, sort_keys=True, separators=(',', ':')).encode()).hexdigest()

def verify_chain(events: tuple[Event, ...], *, expected_tip: str) -> bool:
    fingerprint(expected_tip)
    if not events:
        raise ContractError('Empty audit chain')
    anchor = events[0].tenant, events[0].operation_id
    prev = None
    for i, e in enumerate(events, 1):
        if (e.tenant, e.operation_id) != anchor or e.version != i or e.previous_digest != prev:
            raise ContractError('Broken audit sequence or tenant boundary')
        prev = digest(e)
    return hmac.compare_digest(prev, expected_tip)

@dataclass(frozen=True, slots=True)
class OutboxMessage:
    company_id: UUID
    event_id: UUID
    operation_id: str
    event_digest: str
    topic: str


def propose_outbox(event: Event) -> OutboxMessage:
    if event.kind not in {'submitted', 'unknown', 'settled', 'failed', 'reversed'}:
        raise ContractError('Event has no approved outbox topic')
    return OutboxMessage(event.tenant.company_id, event.event_id, event.operation_id,
                         digest(event), f'finance.review.{event.kind}')
