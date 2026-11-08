"""Phase 39: deterministic balanced journal proposals; no database I/O."""
from __future__ import annotations
from dataclasses import dataclass
from decimal import Decimal
from .contracts import Money, TenantKey, ContractError, amount, reference

COMPONENTS = ('principal', 'interest', 'permitted_charges')
ZERO = Decimal('0.00')

@dataclass(frozen=True, slots=True)
class ApprovedAllocationPolicy:
    policy_id: str
    order: tuple[str, ...]
    account_map: tuple[tuple[str, str], ...]
    clearing_account: str
    approved: bool

    def __post_init__(self):
        reference(self.policy_id)
        if not self.approved or len(self.order) != 3 or set(self.order) != set(COMPONENTS):
            raise ContractError('Complete independently approved policy required')
        mapping = dict(self.account_map)
        if len(mapping) != 3 or set(mapping) != set(COMPONENTS):
            raise ContractError('Complete accounting map required')
        if not self.clearing_account or any(not account for account in mapping.values()):
            raise ContractError('Account missing')
        if len(set((*mapping.values(), self.clearing_account))) != 4:
            raise ContractError('Account collision')

@dataclass(frozen=True, slots=True)
class Line:
    account: str
    side: str
    amount: Money

@dataclass(frozen=True, slots=True)
class Journal:
    tenant: TenantKey
    operation_id: str
    posting_key: str
    policy_id: str
    lines: tuple[Line, ...]


def validate_balanced(journal: Journal) -> None:
    if not journal.lines or not isinstance(journal.tenant, TenantKey):
        raise ContractError('Empty or unscoped journal')
    debits = sum((line.amount.value for line in journal.lines if line.side == 'debit'), ZERO)
    credits = sum((line.amount.value for line in journal.lines if line.side == 'credit'), ZERO)
    if any(line.side not in {'debit','credit'} or not line.account for line in journal.lines):
        raise ContractError('Invalid line')
    if debits <= ZERO or debits != credits:
        raise ContractError('Imbalanced double-entry journal')

def propose_settlement_journal(*, tenant: TenantKey, operation_id: str, posting_key: str,
                               payment: Money, component_balances: dict[str, Decimal],
                               policy: ApprovedAllocationPolicy) -> Journal:
    reference(operation_id)
    reference(posting_key)
    if set(component_balances) != set(COMPONENTS):
        raise ContractError('Complete balances required')
    for value in component_balances.values():
        amount(value, positive=False)
    if payment.value > sum(component_balances.values(), ZERO):
        raise ContractError('Overpayment requires a separate approved process')
    remaining = payment.value
    components = {name: ZERO for name in COMPONENTS}
    for name in policy.order:
        allocated = min(remaining, component_balances[name])
        components[name] = allocated
        remaining -= allocated
    if remaining != ZERO:
        raise ContractError('Unallocated money')
    accounts = dict(policy.account_map)
    lines = [Line(policy.clearing_account, 'debit', payment)]
    for name in policy.order:
        if components[name]:
            lines.append(Line(accounts[name], 'credit', Money(components[name])))
    journal = Journal(tenant, operation_id, posting_key, policy.policy_id, tuple(lines))
    validate_balanced(journal)
    return journal

def propose_full_reversal(original: Journal, *, reversal_key: str) -> Journal:
    reference(reversal_key)
    if reversal_key == original.posting_key:
        raise ContractError('Reversal needs independent unique posting key')
    swapped = tuple(Line(line.account, 'credit' if line.side == 'debit' else 'debit',
                         line.amount) for line in original.lines)
    rev = Journal(original.tenant, original.operation_id, reversal_key, original.policy_id, swapped)
    validate_balanced(rev)
    return rev
