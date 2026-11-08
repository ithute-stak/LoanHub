"""Caller-owned PostgreSQL callback deduplication; no HTTP/network handler."""
from remaining_engine.contracts import ContractError, reference
from .callback_intake import AuthenticatedCallback

def stage_provider_event(db, event: AuthenticatedCallback, *, verified_company_id,
                         enabled: bool = False) -> str:
    if not enabled:
        raise ContractError('Provider event storage disabled')
    if not event.authenticated or event.tenant.company_id != verified_company_id:
        raise ContractError('Unverified callback or wrong tenant')
    for value in (event.event_id,event.operation_id,event.provider_tx_id):
        reference(value)
    params = {'company':str(event.tenant.company_id),'provider':event.provider,
              'event':event.event_id,'operation':event.operation_id,
              'provider_tx':event.provider_tx_id,'digest':event.raw_digest,
              'outcome':event.outcome,'amount':event.money.value}
    found = db.execute('INSERT INTO phase42_provider_events '
                       '(company_id,provider,event_id,operation_id,provider_tx_id,raw_digest,outcome,amount) '
                       'VALUES (%(company)s,%(provider)s,%(event)s,%(operation)s,%(provider_tx)s,%(digest)s,%(outcome)s,%(amount)s) '
                       'ON CONFLICT (company_id,provider,event_id) DO NOTHING RETURNING raw_digest',params).fetchone()
    if found is not None:
        return 'created'
    existing = db.execute('SELECT raw_digest,operation_id,provider_tx_id,outcome,amount '
                          'FROM phase42_provider_events WHERE company_id=%(company)s '
                          'AND provider=%(provider)s AND event_id=%(event)s FOR UPDATE',params).fetchone()
    if not existing:
        raise ContractError('Event disappeared after conflict')
    if existing != (event.raw_digest,event.operation_id,event.provider_tx_id,
                    event.outcome,event.money.value):
        raise ContractError('Conflicting callback reuse')
    return 'replay'
