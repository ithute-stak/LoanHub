"""Reconciliation dispute/recovery reducer; no provider calls or financial posting."""
from dataclasses import dataclass,replace
from decimal import Decimal
from enum import Enum
from datetime import datetime

class DisputeError(ValueError):
    pass

class CaseState(str,Enum):
    OPEN='open'
    UNDER_REVIEW='under_review'
    AWAITING_PROVIDER='awaiting_provider'
    RESOLVED_MATCHED='resolved_matched'
    RESOLVED_REVERSAL='resolved_reversal'
    ESCALATED='escalated'

class CaseAction(str,Enum):
    BEGIN_REVIEW='begin_review'
    REQUEST_PROVIDER_EVIDENCE='request_provider_evidence'
    RESOLVE_MATCHED='resolve_matched'
    RESOLVE_REVERSAL='resolve_reversal'
    ESCALATE='escalate'

ROUTES={
    (CaseState.OPEN,CaseAction.BEGIN_REVIEW):CaseState.UNDER_REVIEW,
    (CaseState.UNDER_REVIEW,CaseAction.REQUEST_PROVIDER_EVIDENCE):CaseState.AWAITING_PROVIDER,
    (CaseState.AWAITING_PROVIDER,CaseAction.BEGIN_REVIEW):CaseState.UNDER_REVIEW,
    (CaseState.UNDER_REVIEW,CaseAction.RESOLVE_MATCHED):CaseState.RESOLVED_MATCHED,
    (CaseState.UNDER_REVIEW,CaseAction.RESOLVE_REVERSAL):CaseState.RESOLVED_REVERSAL,
    (CaseState.OPEN,CaseAction.ESCALATE):CaseState.ESCALATED,
    (CaseState.UNDER_REVIEW,CaseAction.ESCALATE):CaseState.ESCALATED,
    (CaseState.AWAITING_PROVIDER,CaseAction.ESCALATE):CaseState.ESCALATED,
}
@dataclass(frozen=True,slots=True)
class DisputeCase:
    case_id:str
    operation_id:str
    state:CaseState
    version:int
    amount:Decimal
    evidence_refs:tuple[str,...]
    reviewer_id:str|None=None
    resolved_at:datetime|None=None

def advance(case:DisputeCase,action:CaseAction,*,expected_version:int,
            actor_id:str,evidence_ref:str|None=None,now:datetime|None=None,
            approved_reversal:bool=False)->DisputeCase:
    if not isinstance(case,DisputeCase) or not isinstance(action,CaseAction):
        raise DisputeError('Invalid case/action')
    if type(expected_version) is not int or case.version != expected_version:
        raise DisputeError('Stale case version')
    if not isinstance(actor_id,str) or len(actor_id)<8:
        raise DisputeError('Authenticated reviewer required')
    if not isinstance(case.amount,Decimal) or not case.amount.is_finite() or case.amount <= 0:
        raise DisputeError('Invalid disputed amount')
    new=ROUTES.get((case.state,action))
    if new is None:
        raise DisputeError('Illegal transition')
    refs=case.evidence_refs
    if evidence_ref is not None:
        if not isinstance(evidence_ref,str) or len(evidence_ref)<8 or evidence_ref in refs:
            raise DisputeError('Invalid or duplicate evidence')
        refs=(*refs,evidence_ref)
    if new in {CaseState.RESOLVED_MATCHED,CaseState.RESOLVED_REVERSAL}:
        if not refs or now is None or now.tzinfo is None:
            raise DisputeError('Time and provider/ledger evidence required')
    if new==CaseState.RESOLVED_REVERSAL and not approved_reversal:
        raise DisputeError('Independent reversal approval required')
    return replace(case,state=new,version=case.version+1,
                   reviewer_id=actor_id,evidence_refs=refs,
                   resolved_at=now if new in {CaseState.RESOLVED_MATCHED,CaseState.RESOLVED_REVERSAL} else None)
