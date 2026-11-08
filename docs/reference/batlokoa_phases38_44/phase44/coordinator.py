"""Offline-only end-to-end payment STATE simulation.

No provider calls. No production API. Real mandates, provider evidence,
ledger accounts, reconciliation and user scopes MUST be verified externally.
This module intentionally cannot debit or settle real money.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from hashlib import sha256
from uuid import UUID, uuid4
import json
import sqlite3

from .contracts import (BoundaryError, Collection, MandateAttestation,
                        ProviderAttestation, money, opaque, uuid)
from .store import Store


class StateError(BoundaryError):
    pass


@dataclass(frozen=True)
class Result:
    operation_id: str
    status: str
    repeated: bool = False


def _audit(db, company: str, operation: str, action: str, details: dict):
    row = db.execute('SELECT sequence,digest FROM audit WHERE company=? AND operation=? '
                     'ORDER BY sequence DESC LIMIT 1', (company, operation)).fetchone()
    seq = int(row['sequence']) + 1 if row else 1
    previous = row['digest'] if row else None
    body = json.dumps({'v':1, 'company':company,'operation':operation,
                       'sequence':seq,'action':action,'details':details,'previous':previous},
                      sort_keys=True, separators=(',', ':'))
    digest = sha256(body.encode()).hexdigest()
    db.execute('INSERT INTO audit VALUES(?,?,?,?,?,?,?)',
               (company, operation, seq, action, previous, body, digest))


def _outbox(db, company: str, operation: str, event_key: str, topic: str, payload: dict):
    db.execute('INSERT INTO outbox(id,company,operation,topic,event_key,payload) VALUES(?,?,?,?,?,?)',
               (str(uuid4()), company, operation, topic, event_key,
                json.dumps(payload, sort_keys=True, separators=(',', ':'))))


def _row(db, company: str, operation: str):
    r = db.execute('SELECT * FROM collections WHERE company=? AND operation=?',
                   (company, operation)).fetchone()
    if not r:
        raise StateError('Operation not found in verified company scope')
    return r


def _cas(db, row, target: str, provider_ref=None):
    updated = db.execute('UPDATE collections SET state=?,version=version+1,provider_ref=COALESCE(?,provider_ref) '
                         'WHERE company=? AND operation=? AND version=? AND state=?',
                         (target,provider_ref,row['company'],row['operation'],row['version'],row['state']))
    if updated.rowcount != 1:
        raise StateError('Concurrent or stale state change')


class Coordinator:
    def __init__(self, store: Store, *, enabled: bool = False):
        self.store = store
        self.enabled = enabled

    def _enabled(self):
        if not self.enabled:
            raise StateError('Offline financial simulation disabled')

    def reserve(self, collection: Collection, *, verified_company_id: UUID) -> Result:
        self._enabled()
        if not isinstance(collection, Collection) or verified_company_id != collection.company_id:
            raise StateError('Trusted company scope mismatch')
        company = uuid(collection.company_id)
        with self.store.tx() as db:
            keyrow = db.execute('SELECT * FROM collections WHERE company=? AND idempotency_key=?',
                                (company, collection.idempotency_key)).fetchone()
            if keyrow:
                if keyrow['fingerprint'] != collection.fingerprint or keyrow['operation'] != collection.operation_id:
                    raise StateError('Idempotency collision: request differs')
                return Result(collection.operation_id, keyrow['state'], True)
            if db.execute('SELECT 1 FROM collections WHERE company=? AND operation=?',
                          (company, collection.operation_id)).fetchone():
                raise StateError('Existing operation cannot use a new request key')
            db.execute('INSERT INTO collections(company,operation,loan,borrower,idempotency_key,fingerprint,amount,policy,state) '
                       'VALUES(?,?,?,?,?,?,?,?,?)',
                       (company,collection.operation_id,uuid(collection.loan_id),uuid(collection.borrower_id),
                        collection.idempotency_key,collection.fingerprint,money(collection.amount),
                        collection.policy_version,'reserved'))
            _audit(db, company, collection.operation_id, 'reserved',
                   {'fingerprint':collection.fingerprint})
            return Result(collection.operation_id, 'reserved')

    def authorize(self, collection: Collection, mandate: MandateAttestation,
                  *, verified_company_id: UUID) -> Result:
        self._enabled()
        if not isinstance(mandate, MandateAttestation) or collection.company_id != verified_company_id:
            raise StateError('Verified company and mandate required')
        if (mandate.company_id != collection.company_id or
            mandate.operation_id != collection.operation_id or
            mandate.amount_limit < collection.amount):
            raise StateError('Mandate does not authorize operation')
        with self.store.tx() as db:
            row = _row(db, uuid(collection.company_id), collection.operation_id)
            if row['state'] != 'reserved' or row['fingerprint'] != collection.fingerprint:
                raise StateError('Mandate state or request mismatch')
            _cas(db,row,'authorized')
            _audit(db,row['company'],row['operation'],'mandate_verified',
                   {'mandate_ref':mandate.mandate_id})
            return Result(row['operation'],'authorized')

    def submit_intent(self, *, company_id: UUID, operation_id: str,
                      provider_id: str, independent_approval: bool) -> Result:
        """Mark submitted after separate service authorizes sending; sends NOTHING."""
        self._enabled()
        company = uuid(company_id)
        opaque(operation_id); opaque(provider_id)
        if independent_approval is not True:
            raise StateError('Independent provider submission approval required')
        with self.store.tx() as db:
            row=_row(db,company,operation_id)
            if row['state'] != 'authorized':
                raise StateError('Already submitted or not authorized')
            _cas(db,row,'submitted')
            db.execute('UPDATE collections SET provider_id=? WHERE company=? AND operation=?',
                       (provider_id,company,operation_id))
            _audit(db,company,operation_id,'submitted_intent',{'provider':provider_id})
            _outbox(db,company,operation_id,'submit:'+operation_id,'review.provider.submission',
                    {'operation':operation_id,'provider':provider_id,'execution_enabled':False})
            return Result(operation_id,'submitted')

    def timeout_unknown(self, *, company_id: UUID, operation_id: str) -> Result:
        self._enabled()
        company=uuid(company_id); opaque(operation_id)
        with self.store.tx() as db:
            row=_row(db,company,operation_id)
            if row['state'] != 'submitted':
                raise StateError('Only submitted operation can become unknown')
            _cas(db,row,'unknown')
            _audit(db,company,operation_id,'unknown_no_retry',{})
            return Result(operation_id,'unknown')

    def ingest(self, evidence: ProviderAttestation, *, verified_company_id: UUID) -> Result:
        self._enabled()
        if not isinstance(evidence, ProviderAttestation) or evidence.company_id != verified_company_id:
            raise StateError('Verified company and provider evidence required')
        company = uuid(verified_company_id)
        with self.store.tx() as db:
            row=_row(db,company,evidence.operation_id)
            if Decimal(row['amount']) != evidence.amount:
                raise StateError('Provider amount mismatch')
            if row['provider_id'] != evidence.provider_id:
                raise StateError('Provider identity is not bound to submitted operation')
            event = db.execute('SELECT * FROM events WHERE company=? AND provider=? AND event_id=?',
                               (company,evidence.provider_id,evidence.event_id)).fetchone()
            if event:
                if (event['operation'] != evidence.operation_id or
                    event['fingerprint'] != evidence.payload_digest or
                    event['outcome'] != evidence.outcome):
                    raise StateError('Provider event ID conflict')
                return Result(evidence.operation_id,row['state'],True)
            expected = {'settled': ('submitted','unknown'),
                        'failed': ('submitted','unknown'),
                        'reversed': ('reversal_pending',)}[evidence.outcome]
            if row['state'] not in expected:
                raise StateError('Forbidden provider transition')
            if row['provider_ref'] and row['provider_ref'] != evidence.provider_reference:
                raise StateError('Provider reference changed')
            db.execute('INSERT INTO events VALUES(?,?,?,?,?,?)',
                       (company,evidence.provider_id,evidence.event_id,evidence.operation_id,
                        evidence.payload_digest,evidence.outcome))
            new_state = 'reversed' if evidence.outcome == 'reversed' else evidence.outcome
            _cas(db,row,new_state,evidence.provider_reference)
            _audit(db,company,evidence.operation_id,'provider_'+evidence.outcome,
                   {'event_hash':evidence.payload_digest,'provider':evidence.provider_id})
            _outbox(db,company,evidence.operation_id,'provider:'+evidence.provider_id+':'+evidence.event_id,
                    'finance.provider.evidence',{'outcome':evidence.outcome,
                                                'operation':evidence.operation_id,'posting_enabled':False})
            return Result(evidence.operation_id,new_state)

    def request_reversal(self, *, company_id: UUID, operation_id: str,
                         independent_approval: bool) -> Result:
        self._enabled()
        company=uuid(company_id); opaque(operation_id)
        if independent_approval is not True:
            raise StateError('Separate reversal approval required')
        with self.store.tx() as db:
            row=_row(db,company,operation_id)
            if row['state'] != 'settled':
                raise StateError('Only settled operations can request reversal')
            _cas(db,row,'reversal_pending')
            _audit(db,company,operation_id,'reversal_requested',{})
            return Result(operation_id,'reversal_pending')

    def propose_journal(self, *, company_id: UUID, operation_id: str,
                        verified_reconciliation: bool, approved_policy: bool,
                        posting_key: str, allocations: dict[str,Decimal],
                        account_map: dict[str,str]) -> Result:
        """Atomically stage a BALANCED journal proposal. Never posts to real finance."""
        self._enabled()
        company=uuid(company_id); opaque(operation_id); opaque(posting_key)
        if verified_reconciliation is not True or approved_policy is not True:
            raise StateError('Reconciliation and approved allocation policy required')
        if not isinstance(allocations,dict) or not allocations or set(allocations)!=set(account_map):
            raise StateError('Complete account map required')
        for v in account_map.values():
            opaque(v)
        if len(set(account_map.values())) != len(account_map) or 'clearing_receivable' in account_map.values():
            raise StateError('Distinct financial accounts required')
        with self.store.tx() as db:
            row=_row(db,company,operation_id)
            if row['state'] != 'settled':
                raise StateError('Only settled operation may propose journal')
            if db.execute("SELECT 1 FROM journal WHERE company=? AND operation=? AND kind='settlement'",
                          (company,operation_id)).fetchone():
                raise StateError('Operation already has a journal')
            total=Decimal('0.00')
            lines=[('clearing_receivable','debit',row['amount'])]
            for component in sorted(allocations):
                amount=allocations[component]
                if not isinstance(amount,Decimal) or not amount.is_finite() or amount < 0 or amount != amount.quantize(Decimal('0.01')):
                    raise StateError('Invalid allocation amount')
                if amount:
                    lines.append((account_map[component],'credit',format(amount,'.2f')))
                total+=amount
            if total != Decimal(row['amount']) or len(lines)<2:
                raise StateError('Journal not balanced against verified settlement')
            db.execute('INSERT INTO journal VALUES(?,?,?,?,?)',
                       (company,operation_id,posting_key,row['policy'],'settlement'))
            for n,(account,side,amount) in enumerate(lines,1):
                db.execute('INSERT INTO journal_lines VALUES(?,?,?,?,?,?)',
                           (company,posting_key,n,account,side,amount))
            _audit(db,company,operation_id,'journal_proposed',{'posting_key':posting_key})
            _outbox(db,company,operation_id,'journal:'+posting_key,'finance.review.proposal',
                    {'operation':operation_id,'posting_key':posting_key,'posted':False})
            return Result(operation_id,'journal_proposed')

    def propose_reversal_journal(self, *, company_id: UUID, operation_id: str,
                                 posting_key: str, independent_approval: bool,
                                 verified_reversal_evidence: bool) -> Result:
        """Synthetic equal-and-opposite journal proposal, no accounting posting.

        Requires original settlement proposal and a verified provider reversal.
        """
        self._enabled()
        company=uuid(company_id); opaque(operation_id); opaque(posting_key)
        if independent_approval is not True or verified_reversal_evidence is not True:
            raise StateError('Independent approval and matched reversal evidence required')
        with self.store.tx() as db:
            row=_row(db,company,operation_id)
            if row['state'] != 'reversed':
                raise StateError('A verified reversal is required')
            original=db.execute(
                "SELECT * FROM journal WHERE company=? AND operation=? AND kind='settlement'",
                (company,operation_id)).fetchone()
            if not original:
                raise StateError('Original journal absent: manual accounting review required')
            if db.execute("SELECT 1 FROM journal WHERE company=? AND operation=? AND kind='reversal'",
                          (company,operation_id)).fetchone():
                raise StateError('Reversal journal already exists')
            lines=db.execute('SELECT * FROM journal_lines WHERE company=? AND posting_key=? ORDER BY number',
                             (company,original['posting_key'])).fetchall()
            if len(lines)<2:
                raise StateError('Original accounting evidence incomplete')
            debit=sum((Decimal(x['amount']) for x in lines if x['side']=='debit'),Decimal('0.00'))
            credit=sum((Decimal(x['amount']) for x in lines if x['side']=='credit'),Decimal('0.00'))
            if debit != credit or debit != Decimal(row['amount']):
                raise StateError('Original journal unbalanced or amount mismatch')
            db.execute('INSERT INTO journal VALUES(?,?,?,?,?)',
                       (company,operation_id,posting_key,original['policy'],'reversal'))
            for i,line in enumerate(lines,1):
                db.execute('INSERT INTO journal_lines VALUES(?,?,?,?,?,?)',
                           (company,posting_key,i,line['account'],
                            'credit' if line['side']=='debit' else 'debit',line['amount']))
            _audit(db,company,operation_id,'reversal_journal_proposed',{'posting_key':posting_key,
                   'original_posting_key':original['posting_key']})
            _outbox(db,company,operation_id,'journal:'+posting_key,'finance.review.reversal',
                    {'operation':operation_id,'posting_key':posting_key,'posted':False})
            return Result(operation_id,'reversal_journal_proposed')

    def acknowledge_outbox(self, *, outbox_id: str, accepted: bool) -> None:
        """Test-only ACK; real dispatch requires an authenticated destination adapter."""
        self._enabled()
        with self.store.tx() as db:
            row=db.execute('SELECT state,tries FROM outbox WHERE id=?',(outbox_id,)).fetchone()
            if not row or row['state'] != 'pending':
                raise StateError('Outbox message unavailable')
            tries=row['tries']+1
            state='delivered' if accepted else ('dead' if tries>=5 else 'pending')
            db.execute('UPDATE outbox SET state=?,tries=? WHERE id=?',(state,tries,outbox_id))
