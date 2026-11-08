"""Recalculate synthetic audit chain from trusted local transaction history."""
from hashlib import sha256
import json
from .contracts import BoundaryError


def verify(store, *, company: str, operation: str) -> bool:
    rows=store.conn.execute('SELECT * FROM audit WHERE company=? AND operation=? ORDER BY sequence',
                            (company,operation)).fetchall()
    if not rows:
        raise BoundaryError('Audit chain missing')
    prev=None
    for index,row in enumerate(rows,1):
        if row['sequence'] != index or row['previous_hash'] != prev:
            return False
        try:
            body = json.loads(row['payload'])
            canonical = json.dumps(body, sort_keys=True, separators=(',', ':'))
        except (ValueError, TypeError):
            return False
        if (body.get('company') != company or body.get('operation') != operation
                or body.get('sequence') != index or body.get('action') != row['action']
                or body.get('previous') != prev
                or sha256(canonical.encode()).hexdigest() != row['digest']):
            return False
        prev=row['digest']
    return True
