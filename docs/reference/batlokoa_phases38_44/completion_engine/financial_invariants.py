"""Cross-component settlement and reversal invariants."""
from dataclasses import dataclass
from decimal import Decimal
from remaining_engine.contracts import ContractError, TenantKey, Money, reference
from remaining_engine.ledger_posting import Journal, validate_balanced
from remaining_engine.transaction_integrity import Transaction, Status
from remaining_engine.reconciliation import Finding, Decision

@dataclass(frozen=True,slots=True)
class PostingAuthorization:
    operation_id: str
    posting_key: str
    reconciled_reference: str
    tenant: TenantKey
    allowed: bool
    reviewed_by: str

def assert_settlement_ready(*, transaction: Transaction, journal: Journal,
                            finding: Finding, authorization: PostingAuthorization) -> None:
    if transaction.status is not Status.SETTLED:
        raise ContractError('Unsettled operation cannot post')
    if finding.decision is not Decision.MATCHED or finding.operation_id != transaction.operation_id:
        raise ContractError('Unreconciled provider settlement')
    if not authorization.allowed or not authorization.reviewed_by:
        raise ContractError('Independent financial approval missing')
    if (authorization.operation_id != transaction.operation_id or
        authorization.tenant != transaction.tenant or
        authorization.posting_key != journal.posting_key or
        authorization.reconciled_reference != finding.operation_id):
        raise ContractError('Authorization does not bind to journal')
    if journal.tenant != transaction.tenant or journal.operation_id != transaction.operation_id:
        raise ContractError('Cross-tenant or cross-operation journal')
    validate_balanced(journal)
    debits = sum((x.amount.value for x in journal.lines if x.side=='debit'),Decimal('0.00'))
    if debits != transaction.money.value:
        raise ContractError('Journal amount differs from settlement')

def assert_full_reversal(original: Journal, reversed_journal: Journal) -> None:
    validate_balanced(original);validate_balanced(reversed_journal)
    if original.tenant != reversed_journal.tenant or original.operation_id != reversed_journal.operation_id:
        raise ContractError('Cross-tenant reversal')
    if original.posting_key == reversed_journal.posting_key:
        raise ContractError('Duplicate posting key')
    expected = sorted((x.account, 'credit' if x.side=='debit' else 'debit', x.amount.value)
                      for x in original.lines)
    actual = sorted((x.account, x.side, x.amount.value) for x in reversed_journal.lines)
    if expected != actual:
        raise ContractError('Reversal not equal and opposite')
