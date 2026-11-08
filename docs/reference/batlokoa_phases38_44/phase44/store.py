"""Transactional local simulated store. NEVER use for real money or shared deployment.

SQLite exercises rollback and uniqueness semantics only; production requires
PostgreSQL row locks, real tenant RLS, and audited migrations.
"""
from __future__ import annotations
import sqlite3
from contextlib import contextmanager
from decimal import Decimal
from uuid import uuid4

DDL = '''
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS collections (
  company TEXT NOT NULL,
  operation TEXT NOT NULL,
  loan TEXT NOT NULL,
  borrower TEXT NOT NULL,
  idempotency_key TEXT NOT NULL,
  fingerprint TEXT NOT NULL,
  amount TEXT NOT NULL,
  policy TEXT NOT NULL,
  state TEXT NOT NULL CHECK(state IN
    ('reserved','authorized','submitted','unknown','failed','settled','reversal_pending','reversed')),
  version INTEGER NOT NULL DEFAULT 0 CHECK(version >= 0),
  provider_ref TEXT,
  provider_id TEXT,
  PRIMARY KEY(company,operation),
  UNIQUE(company,idempotency_key)
);
CREATE TABLE IF NOT EXISTS events (
  company TEXT NOT NULL,
  provider TEXT NOT NULL,
  event_id TEXT NOT NULL,
  operation TEXT NOT NULL,
  fingerprint TEXT NOT NULL,
  outcome TEXT NOT NULL,
  PRIMARY KEY(company,provider,event_id),
  FOREIGN KEY(company,operation) REFERENCES collections(company,operation)
);
CREATE TABLE IF NOT EXISTS journal (
  company TEXT NOT NULL,
  operation TEXT NOT NULL,
  posting_key TEXT NOT NULL,
  policy TEXT NOT NULL,
  kind TEXT NOT NULL CHECK(kind IN ('settlement','reversal')),
  PRIMARY KEY(company,posting_key),
  UNIQUE(company,operation,kind),
  FOREIGN KEY(company,operation) REFERENCES collections(company,operation)
);
CREATE TABLE IF NOT EXISTS journal_lines (
  company TEXT NOT NULL,
  posting_key TEXT NOT NULL,
  number INTEGER NOT NULL,
  account TEXT NOT NULL,
  side TEXT NOT NULL CHECK(side IN ('debit','credit')),
  amount TEXT NOT NULL,
  PRIMARY KEY(company,posting_key,number),
  FOREIGN KEY(company,posting_key) REFERENCES journal(company,posting_key)
);
CREATE TABLE IF NOT EXISTS outbox (
  id TEXT PRIMARY KEY,
  company TEXT NOT NULL,
  operation TEXT NOT NULL,
  topic TEXT NOT NULL,
  event_key TEXT NOT NULL,
  payload TEXT NOT NULL,
  state TEXT NOT NULL DEFAULT 'pending' CHECK(state IN ('pending','delivered','dead')),
  tries INTEGER NOT NULL DEFAULT 0,
  UNIQUE(company,event_key)
);
CREATE TABLE IF NOT EXISTS audit (
  company TEXT NOT NULL,
  operation TEXT NOT NULL,
  sequence INTEGER NOT NULL,
  action TEXT NOT NULL,
  previous_hash TEXT,
  payload TEXT NOT NULL,
  digest TEXT NOT NULL,
  PRIMARY KEY(company,operation,sequence)
);
'''

class Store:
    """Single-process synthetic testing backend, not a payment storage adapter."""
    def __init__(self, path=':memory:'):
        self.conn = sqlite3.connect(path, isolation_level=None)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute('PRAGMA foreign_keys=ON')
        self.conn.executescript(DDL)

    @contextmanager
    def tx(self):
        self.conn.execute('BEGIN IMMEDIATE')
        try:
            yield self.conn
            self.conn.execute('COMMIT')
        except BaseException:
            self.conn.execute('ROLLBACK')
            raise

    def close(self):
        self.conn.close()
