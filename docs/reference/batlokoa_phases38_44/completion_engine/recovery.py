"""Recovery classifier that never guesses unknown provider settlements."""
from dataclasses import dataclass
from enum import Enum
from datetime import datetime, timedelta
from remaining_engine.transaction_integrity import Transaction, Status
from remaining_engine.contracts import ContractError

class RecoveryAction(str,Enum):
    NO_ACTION='no_action'
    INVESTIGATE_PROVIDER='investigate_provider'
    RECONCILE='reconcile'
    REQUIRE_MANUAL_APPROVAL='require_manual_approval'

def classify_recovery(tx: Transaction, *, provider_status_authenticated: bool,
                      reconciled: bool, operator_approved: bool) -> RecoveryAction:
    if tx.status in {Status.FAILED,Status.REVERSED}:
        return RecoveryAction.NO_ACTION
    if tx.status in {Status.SUBMITTED,Status.UNKNOWN}:
        return RecoveryAction.INVESTIGATE_PROVIDER
    if tx.status is Status.SETTLED:
        return RecoveryAction.RECONCILE if not reconciled else RecoveryAction.NO_ACTION
    if tx.status is Status.REVERSAL_REQUESTED:
        return RecoveryAction.REQUIRE_MANUAL_APPROVAL
    return RecoveryAction.NO_ACTION
