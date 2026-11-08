"""Pure Phase 38 lifecycle reducer. No payment submissions or persistence."""
from __future__ import annotations
from dataclasses import dataclass, replace
from enum import Enum
from .contracts import Money, TenantKey, ContractError, reference, fingerprint

class Status(str, Enum):
    RESERVED = 'reserved'
    MANDATE_VERIFIED = 'mandate_verified'
    SUBMITTED = 'submitted'
    UNKNOWN = 'unknown'
    FAILED = 'failed'
    SETTLED = 'settled'
    REVERSAL_REQUESTED = 'reversal_requested'
    REVERSED = 'reversed'

class Command(str, Enum):
    VERIFY_MANDATE = 'verify_mandate'
    SUBMIT = 'submit'
    TIMEOUT = 'timeout'
    PROVIDER_FAILURE = 'provider_failure'
    PROVIDER_SETTLEMENT = 'provider_settlement'
    REQUEST_REVERSAL = 'request_reversal'
    PROVIDER_REVERSAL = 'provider_reversal'

TRANSITIONS = {
    (Status.RESERVED, Command.VERIFY_MANDATE): Status.MANDATE_VERIFIED,
    (Status.MANDATE_VERIFIED, Command.SUBMIT): Status.SUBMITTED,
    (Status.SUBMITTED, Command.TIMEOUT): Status.UNKNOWN,
    (Status.SUBMITTED, Command.PROVIDER_FAILURE): Status.FAILED,
    (Status.UNKNOWN, Command.PROVIDER_FAILURE): Status.FAILED,
    (Status.SUBMITTED, Command.PROVIDER_SETTLEMENT): Status.SETTLED,
    (Status.UNKNOWN, Command.PROVIDER_SETTLEMENT): Status.SETTLED,
    (Status.SETTLED, Command.REQUEST_REVERSAL): Status.REVERSAL_REQUESTED,
    (Status.REVERSAL_REQUESTED, Command.PROVIDER_REVERSAL): Status.REVERSED,
}
EVIDENCE_COMMANDS = {Command.PROVIDER_FAILURE, Command.PROVIDER_SETTLEMENT, Command.PROVIDER_REVERSAL}

class TransitionError(ContractError):
    pass

@dataclass(frozen=True, slots=True)
class Transaction:
    tenant: TenantKey
    money: Money
    operation_id: str
    request_fingerprint: str
    status: Status = Status.RESERVED
    version: int = 0
    provider_reference: str | None = None

    def __post_init__(self):
        reference(self.operation_id)
        fingerprint(self.request_fingerprint)
        if type(self.version) is not int or self.version < 0:
            raise TransitionError('Invalid optimistic version')

@dataclass(frozen=True, slots=True)
class VerifiedMandate:
    tenant: TenantKey
    operation_id: str
    amount: Money
    mandate_reference: str
    approved: bool

@dataclass(frozen=True, slots=True)
class VerifiedProviderResult:
    tenant: TenantKey
    operation_id: str
    amount: Money
    provider_reference: str
    event_reference: str
    outcome: str
    verified: bool

    def __post_init__(self):
        reference(self.provider_reference)
        reference(self.event_reference)
        if self.outcome not in {'settled', 'failed', 'reversed'}:
            raise TransitionError('Unsupported provider outcome')

def transition(tx: Transaction, command: Command, *, expected_version: int,
               mandate: VerifiedMandate | None = None,
               provider: VerifiedProviderResult | None = None,
               independent_reversal_approval: bool = False) -> Transaction:
    if not isinstance(command, Command) or expected_version != tx.version:
        raise TransitionError('Unknown command or stale transaction')
    new = TRANSITIONS.get((tx.status, command))
    if new is None:
        raise TransitionError('Transition forbidden (including duplicate settlement or retry after timeout)')
    if command == Command.VERIFY_MANDATE:
        if (not isinstance(mandate, VerifiedMandate) or not mandate.approved or
            (mandate.tenant, mandate.operation_id, mandate.amount) !=
            (tx.tenant, tx.operation_id, tx.money)):
            raise TransitionError('Independently authenticated, matching borrower mandate required')
        reference(mandate.mandate_reference)
    elif mandate is not None:
        raise TransitionError('Unexpected mandate evidence')
    if command in EVIDENCE_COMMANDS:
        expected_outcome = {
            Command.PROVIDER_FAILURE: 'failed',
            Command.PROVIDER_SETTLEMENT: 'settled',
            Command.PROVIDER_REVERSAL: 'reversed',
        }[command]
        if (not isinstance(provider, VerifiedProviderResult) or not provider.verified
            or provider.outcome != expected_outcome
            or (provider.tenant, provider.operation_id, provider.amount) !=
            (tx.tenant, tx.operation_id, tx.money)):
            raise TransitionError('Matching verified provider evidence required')
        if tx.provider_reference is not None and tx.provider_reference != provider.provider_reference:
            raise TransitionError('Provider reference changed')
    elif provider is not None:
        raise TransitionError('Unexpected provider evidence')
    if command == Command.REQUEST_REVERSAL and not independent_reversal_approval:
        raise TransitionError('Independent reversal approval required')
    return replace(tx, status=new, version=tx.version + 1,
                   provider_reference=(provider.provider_reference if provider else tx.provider_reference))
