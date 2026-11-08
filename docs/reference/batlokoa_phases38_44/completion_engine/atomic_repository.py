"""Disabled-by-default PostgreSQL transaction adapter for standalone TEST schema.

No migrations, provider calls, money movement, or commits. Caller owns one
transaction and must supply a trusted, independently authorized settlement.
"""
from dataclasses import dataclass
from decimal import Decimal
from remaining_engine.contracts import ContractError
from remaining_engine.transaction_integrity import Transaction
from remaining_engine.ledger_posting import Journal
from remaining_engine.reconciliation import Finding
from .financial_invariants import PostingAuthorization, assert_settlement_ready

@dataclass(frozen=True)
class PostingResult:
    posting_key: str
    staged: bool

def stage_atomic_settlement(*, db, transaction: Transaction, journal: Journal,
                            finding: Finding, approval: PostingAuthorization,
                            enabled: bool = False) -> PostingResult:
    if not enabled:
        raise ContractError('Atomic posting disabled')
    assert_settlement_ready(transaction=transaction, journal=journal,
                            finding=finding, authorization=approval)
    params = {'company': str(transaction.tenant.company_id),
              'operation': transaction.operation_id}
    row = db.execute('SELECT version,status,amount FROM phase42_operations '
                     'WHERE company_id=%(company)s AND operation_id=%(operation)s FOR UPDATE', params).fetchone()
    if not row or row[0] != transaction.version or row[1] != 'settled' or Decimal(str(row[2])) != transaction.money.value:
        raise ContractError('Operation missing, stale or mismatched')
    write = {**params, 'posting': journal.posting_key, 'policy': journal.policy_id}
    result = db.execute('INSERT INTO phase42_journals '
                        '(company_id,operation_id,posting_key,policy_id) VALUES '
                        '(%(company)s,%(operation)s,%(posting)s,%(policy)s) '
                        'ON CONFLICT (company_id,posting_key) DO NOTHING RETURNING posting_key', write).fetchone()
    if result is None:
        raise ContractError('Duplicate posting must be inspected, not silently replayed')
    for number,line in enumerate(journal.lines,1):
        db.execute('INSERT INTO phase42_journal_lines '
                   '(company_id,posting_key,line_no,account,side,amount) VALUES '
                   '(%(company)s,%(posting)s,%(number)s,%(account)s,%(side)s,%(amount)s)',
                   {**write,'number':number,'account':line.account,'side':line.side,'amount':line.amount.value})
    db.execute('INSERT INTO phase42_posting_events '
               '(company_id,operation_id,posting_key,kind) VALUES '
               "(%(company)s,%(operation)s,%(posting)s,'journal_proposed')", write)
    db.execute('INSERT INTO phase42_outbox '
               '(company_id,operation_id,posting_key,topic) VALUES '
               "(%(company)s,%(operation)s,%(posting)s,'finance.review.journal')", write)
    return PostingResult(journal.posting_key,True)
