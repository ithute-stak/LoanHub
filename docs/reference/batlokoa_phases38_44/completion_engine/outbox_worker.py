"""Offline non-sending outbox lease/retry contract; no network worker."""
from dataclasses import dataclass,replace
from datetime import datetime,timedelta
from remaining_engine.contracts import ContractError, reference

@dataclass(frozen=True,slots=True)
class OutboxLease:
    event_id: str
    attempts: int
    next_attempt_at: datetime
    leased_until: datetime | None
    status: str

def lease_for_delivery(item: OutboxLease, *, now: datetime, lease_seconds: int=30,
                       max_attempts: int=8) -> OutboxLease:
    reference(item.event_id)
    if item.status not in {'pending','leased','delivered','dead_letter'}:
        raise ContractError('Invalid outbox status')
    if now.tzinfo is None or item.next_attempt_at.tzinfo is None:
        raise ContractError('Timezone aware timestamps required')
    if item.status in {'delivered','dead_letter'}:
        raise ContractError('Terminal outbox item')
    if item.leased_until and item.leased_until > now:
        raise ContractError('Active worker lease')
    if item.next_attempt_at > now:
        raise ContractError('Backoff not elapsed')
    if item.attempts >= max_attempts or lease_seconds <= 0:
        raise ContractError('Retry budget exceeded')
    return replace(item, attempts=item.attempts+1,
                   leased_until=now+timedelta(seconds=lease_seconds),status='leased')

def record_delivery(item: OutboxLease, *, ack: bool, now: datetime, max_attempts:int=8) -> OutboxLease:
    if item.status != 'leased' or item.leased_until is None:
        raise ContractError('Item not currently leased')
    if ack:
        return replace(item,status='delivered',leased_until=None)
    if item.attempts >= max_attempts:
        return replace(item,status='dead_letter',leased_until=None)
    backoff=min(3600,2**min(item.attempts,12))
    return replace(item,status='pending',leased_until=None,next_attempt_at=now+timedelta(seconds=backoff))
