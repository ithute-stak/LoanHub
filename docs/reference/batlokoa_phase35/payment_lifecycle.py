"""FUTURE ONLY: pure lifecycle reducer, not payment execution or storage."""
from __future__ import annotations
from dataclasses import dataclass, replace
from decimal import Decimal
from enum import Enum
from typing import Final

class State(str, Enum):
    RESERVED = "reserved"
    AWAITING_AUTHORIZATION = "awaiting_authorization"
    AUTHORIZED = "authorized"
    SUBMITTED = "submitted"
    UNKNOWN = "unknown"
    FAILED = "failed"
    SETTLED = "settled"
    REVERSAL_PENDING = "reversal_pending"
    REVERSED = "reversed"

class Event(str, Enum):
    REQUIRE_AUTHORIZATION = "require_authorization"
    AUTHORIZE = "authorize"
    SUBMIT = "submit"
    PROVIDER_TIMEOUT = "provider_timeout"
    CONFIRM_FAILURE = "confirm_failure"
    CONFIRM_SETTLEMENT = "confirm_settlement"
    REQUEST_REVERSAL = "request_reversal"
    CONFIRM_REVERSAL = "confirm_reversal"

TRANSITIONS: Final[dict[tuple[State, Event], State]] = {
    (State.RESERVED, Event.REQUIRE_AUTHORIZATION): State.AWAITING_AUTHORIZATION,
    (State.AWAITING_AUTHORIZATION, Event.AUTHORIZE): State.AUTHORIZED,
    (State.AUTHORIZED, Event.SUBMIT): State.SUBMITTED,
    (State.SUBMITTED, Event.PROVIDER_TIMEOUT): State.UNKNOWN,
    (State.SUBMITTED, Event.CONFIRM_FAILURE): State.FAILED,
    (State.UNKNOWN, Event.CONFIRM_FAILURE): State.FAILED,
    (State.SUBMITTED, Event.CONFIRM_SETTLEMENT): State.SETTLED,
    (State.UNKNOWN, Event.CONFIRM_SETTLEMENT): State.SETTLED,
    (State.SETTLED, Event.REQUEST_REVERSAL): State.REVERSAL_PENDING,
    (State.REVERSAL_PENDING, Event.CONFIRM_REVERSAL): State.REVERSED,
}

class InvalidTransition(ValueError):
    pass

@dataclass(frozen=True)
class Lifecycle:
    state: State
    amount: Decimal
    currency: str = "LSL"
    sequence: int = 0
    settled_amount: Decimal = Decimal("0.00")
    reversed_amount: Decimal = Decimal("0.00")

def apply_event(
    record: Lifecycle,
    event: Event,
    *,
    expected_sequence: int,
    settlement_amount: Decimal | None = None,
    reversal_amount: Decimal | None = None,
    authenticated_provider_evidence: bool = False,
    approved_mandate: bool = False,
    approved_reversal: bool = False,
) -> Lifecycle:
    """No I/O. Compare-and-swap and external evidence still required by a future engine."""
    if not isinstance(record, Lifecycle) or not isinstance(record.state, State):
        raise InvalidTransition("Invalid lifecycle record")
    if not isinstance(event, Event):
        raise InvalidTransition("Unknown lifecycle event")
    if not isinstance(expected_sequence, int) or expected_sequence != record.sequence:
        raise InvalidTransition("Stale or replayed lifecycle sequence")
    if not isinstance(record.amount, Decimal) or not record.amount.is_finite() or record.amount <= 0:
        raise InvalidTransition("Invalid transaction amount")
    if record.currency != "LSL" or record.amount != record.amount.quantize(Decimal("0.01")):
        raise InvalidTransition("Invalid transaction currency or precision")
    if (not record.settled_amount.is_finite() or not record.reversed_amount.is_finite()
            or record.settled_amount < 0 or record.reversed_amount < 0
            or record.reversed_amount > record.settled_amount):
        raise InvalidTransition("Inconsistent financial amounts")
    next_state = TRANSITIONS.get((record.state, event))
    if next_state is None:
        raise InvalidTransition("Transition not permitted")
    if event == Event.AUTHORIZE and not approved_mandate:
        raise InvalidTransition("Verified mandate required")
    if event == Event.REQUEST_REVERSAL and not approved_reversal:
        raise InvalidTransition("Independent reversal approval required")
    if event in {Event.CONFIRM_SETTLEMENT, Event.CONFIRM_FAILURE, Event.CONFIRM_REVERSAL}:
        if not authenticated_provider_evidence:
            raise InvalidTransition("Verified provider evidence required")
    if event == Event.CONFIRM_SETTLEMENT:
        if settlement_amount is None or not isinstance(settlement_amount, Decimal):
            raise InvalidTransition("Exact settlement amount required")
        if not settlement_amount.is_finite() or settlement_amount != record.amount:
            raise InvalidTransition("Partial or mismatched settlement requires manual reconciliation")
        return replace(record, state=next_state, sequence=record.sequence + 1,
                       settled_amount=settlement_amount)
    if settlement_amount is not None:
        raise InvalidTransition("Unexpected settlement amount")
    if event == Event.CONFIRM_REVERSAL:
        if reversal_amount is None or not isinstance(reversal_amount, Decimal):
            raise InvalidTransition("Exact reversal amount required")
        if not reversal_amount.is_finite() or reversal_amount != record.settled_amount:
            raise InvalidTransition("Partial or mismatched reversal requires separate workflow")
        return replace(record, state=next_state, sequence=record.sequence + 1,
                       reversed_amount=reversal_amount)
    if reversal_amount is not None:
        raise InvalidTransition("Unexpected reversal amount")
    return replace(record, state=next_state, sequence=record.sequence + 1)
