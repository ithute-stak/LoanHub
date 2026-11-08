"""Real PostgreSQL transaction rollback, duplicate and atomic posting tests.

Run ONLY with a disposable PostgreSQL database and
BATLOKOA_OFFLINE_TEST_POSTGRES_URL explicitly set. Requires psycopg2-binary.
This fixture creates its own random schema and deletes it afterwards.
"""
import os
from pathlib import Path
from decimal import Decimal as D
from uuid import uuid4
import unittest

from .test_completion import C,OP,tx,journal,auth,FakeDB,callback
from remaining_engine.reconciliation import Finding, Decision
from remaining_engine.contracts import ContractError
from completion_engine.atomic_repository import stage_atomic_settlement
from completion_engine.provider_event_store import stage_provider_event

DSN=os.getenv('BATLOKOA_OFFLINE_TEST_POSTGRES_URL')
try:
    import psycopg2
except ImportError:
    psycopg2=None

class PsycopgExecution:
    def __init__(self,conn): self.conn=conn
    def execute(self,statement,params):
        cursor=self.conn.cursor()
        cursor.execute(statement,params)
        return cursor

@unittest.skipUnless(DSN and psycopg2, 'Requires explicit disposable PostgreSQL DSN and psycopg2')
class PostgresIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema='phase42_ci_'+uuid4().hex
        cls.dsn=DSN
        with psycopg2.connect(cls.dsn) as conn:
            with conn.cursor() as cur:
                cur.execute('CREATE SCHEMA "'+cls.schema+'"')
        try:
            cls.create_fixture()
        except Exception:
            cls.tearDownClass()
            raise

    @classmethod
    def conn(cls):
        connection=psycopg2.connect(cls.dsn)
        with connection.cursor() as cur:
            cur.execute('SET search_path TO "'+cls.schema+'"')
        return connection

    @classmethod
    def create_fixture(cls):
        statements=(Path(__file__).resolve().parents[1]/'schemas'/'phase42_isolated_postgres.sql').read_text()
        with cls.conn() as conn:
            with conn.cursor() as cur:
                cur.execute(statements)

    @classmethod
    def tearDownClass(cls):
        with psycopg2.connect(cls.dsn) as conn:
            with conn.cursor() as cur:
                cur.execute('DROP SCHEMA IF EXISTS "'+cls.schema+'" CASCADE')

    def setUp(self):
        with self.conn() as conn:
            with conn.cursor() as cur:
                cur.execute('INSERT INTO phase42_operations (company_id,operation_id,version,status,amount) '
                            'VALUES (%s,%s,4,%s,80.00) ON CONFLICT DO NOTHING',(str(C),OP,'settled'))

    def test_atomic_journal_event_outbox_and_rollback(self):
        c=self.conn()
        try:
            db=PsycopgExecution(c)
            result=stage_atomic_settlement(db=db,transaction=tx(),journal=journal(),
                finding=Finding(OP,Decision.MATCHED,False),approval=auth(),enabled=True)
            self.assertTrue(result.staged)
            with c.cursor() as cur:
                for table in ('phase42_journals','phase42_posting_events','phase42_outbox'):
                    cur.execute('SELECT count(*) FROM '+table)
                    self.assertEqual(cur.fetchone()[0],1)
            c.rollback()
        finally:
            c.close()
        with self.conn() as conn:
            with conn.cursor() as cur:
                cur.execute('SELECT count(*) FROM phase42_journals')
                self.assertEqual(cur.fetchone()[0],0)

    def test_duplicate_key_is_rejected(self):
        with self.conn() as conn:
            db=PsycopgExecution(conn)
            stage_atomic_settlement(db=db,transaction=tx(),journal=journal(),
                finding=Finding(OP,Decision.MATCHED,False),approval=auth(),enabled=True)
            with self.assertRaises(ContractError):
                stage_atomic_settlement(db=db,transaction=tx(),journal=journal(),
                    finding=Finding(OP,Decision.MATCHED,False),approval=auth(),enabled=True)
            conn.rollback()

    def test_callback_insert_and_replay(self):
        with self.conn() as conn:
            db=PsycopgExecution(conn)
            event=callback()
            self.assertEqual(stage_provider_event(db,event,verified_company_id=C,enabled=True),'created')
            self.assertEqual(stage_provider_event(db,event,verified_company_id=C,enabled=True),'replay')
            conn.rollback()
