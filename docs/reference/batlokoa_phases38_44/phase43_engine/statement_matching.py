"""Deterministic, read-only provider/internal statement exception matching."""
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum

class StatementError(ValueError): pass
class Outcome(str,Enum):
    MATCHED='matched'
    PROVIDER_ONLY='provider_only'
    INTERNAL_ONLY='internal_only'
    DUPLICATE_PROVIDER='duplicate_provider'
    DUPLICATE_INTERNAL='duplicate_internal'
    AMOUNT_MISMATCH='amount_mismatch'
    CURRENCY_MISMATCH='currency_mismatch'
    STATUS_MISMATCH='status_mismatch'

@dataclass(frozen=True,slots=True)
class Entry:
    company_id:str
    provider_id:str
    provider_reference:str
    operation_id:str
    amount:Decimal
    currency:str
    status:str

@dataclass(frozen=True,slots=True)
class Match:
    key:tuple[str,str,str]
    result:Outcome
    internal_amount:Decimal|None
    provider_amount:Decimal|None

def match_statements(internal:tuple[Entry,...],provider:tuple[Entry,...])->tuple[Match,...]:
    by_i={};by_p={}
    for rows,store in ((internal,by_i),(provider,by_p)):
        if not isinstance(rows,tuple):raise StatementError('Immutable tuple of records required')
        for r in rows:
            if not isinstance(r,Entry) or not all(isinstance(x,str) and x for x in (
                r.company_id,r.provider_id,r.provider_reference,r.operation_id,r.currency,r.status)):
                raise StatementError('Incomplete statement identity')
            if not isinstance(r.amount,Decimal) or not r.amount.is_finite() or r.amount <= 0 or r.amount.as_tuple().exponent < -2:
                raise StatementError('Invalid amount')
            store.setdefault((r.company_id,r.provider_id,r.provider_reference),[]).append(r)
    output=[]
    for key in sorted(set(by_i)|set(by_p)):
        left=by_i.get(key,[]);right=by_p.get(key,[])
        a=left[0].amount if len(left)==1 else None
        b=right[0].amount if len(right)==1 else None
        if len(left)>1:result=Outcome.DUPLICATE_INTERNAL
        elif len(right)>1:result=Outcome.DUPLICATE_PROVIDER
        elif not left:result=Outcome.PROVIDER_ONLY
        elif not right:result=Outcome.INTERNAL_ONLY
        elif left[0].operation_id!=right[0].operation_id:result=Outcome.STATUS_MISMATCH
        elif left[0].currency!=right[0].currency or left[0].currency!='LSL':result=Outcome.CURRENCY_MISMATCH
        elif a!=b:result=Outcome.AMOUNT_MISMATCH
        elif left[0].status!=right[0].status or left[0].status!='settled':result=Outcome.STATUS_MISMATCH
        else:result=Outcome.MATCHED
        output.append(Match(key,result,a,b))
    return tuple(output)
