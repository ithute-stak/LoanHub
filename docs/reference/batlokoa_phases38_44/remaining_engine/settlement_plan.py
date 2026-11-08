"""Phase 39/40 pure settlement posting plan. No ledger DB insert is performed."""
from __future__ import annotations
from dataclasses import dataclass
from decimal import Decimal
from .contracts import ContractError
from .transaction_integrity import Transaction, Status
from .reconciliation import Finding, Decision
from .ledger_posting import (ApprovedAllocationPolicy, Journal,
                              propose_settlement_journal)

@dataclass(frozen=True, slots=True)
class SettlementPlan:
    journal: Journal
    operation_version: int
    source_decision: Decision
    requires_database_lock: bool = True
    requires_unique_posting_key: bool = True


def propose_posting(*, transaction: Transaction, finding: Finding,
                    component_balances: dict[str, Decimal],
                    approved_policy: ApprovedAllocationPolicy,
                    unique_posting_key: str) -> SettlementPlan:
    if transaction.status is not Status.SETTLED:
        raise ContractError('Only fully verified settlement may propose posting')
    if finding.operation_id != transaction.operation_id or finding.decision is not Decision.MATCHED:
        raise ContractError('Reconciliation evidence not matched')
    journal = propose_settlement_journal(
        tenant=transaction.tenant, operation_id=transaction.operation_id,
        posting_key=unique_posting_key, payment=transaction.money,
        component_balances=component_balances, policy=approved_policy,
    )
    return SettlementPlan(journal, transaction.version, finding.decision)
