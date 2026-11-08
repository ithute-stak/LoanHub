from dataclasses import replace
from decimal import Decimal
from hashlib import sha256
import sqlite3
import tempfile
import unittest
from uuid import UUID

from phase44.contracts import (Collection, MandateAttestation, ProviderAttestation,
                               BoundaryError)
from phase44.store import Store
from phase44.coordinator import Coordinator, StateError
from phase44.audit import verify

A=UUID('4236a21f-5164-48aa-90f3-a35eccd23ae2')
B=UUID('00000000-0000-4000-8000-000000000002')
L=UUID('00000000-0000-4000-8000-000000000003')
BORROWER=UUID('00000000-0000-4000-8000-000000000004')


def collection(company=A, **changes):
    return Collection(company,L,BORROWER,'op_TEST_12345678','idempotency_TEST_12345678',
                      Decimal('100.00'),'policy_2026_v1',**changes)


def mandate(company=A, operation='op_TEST_12345678', limit='100.00'):
    return MandateAttestation(company,operation,'mandate_TEST_12345678',Decimal(limit),True)


def provider(company=A, outcome='settled', event='evt_TEST_12345678', operation='op_TEST_12345678',
             amount='100.00', digest='a'*64, reference='prov_ref_12345678'):
    return ProviderAttestation(company,operation,'VODACOM_TEST_ONLY',event,reference,
                               Decimal(amount),outcome,digest,True)


class Phase44Tests(unittest.TestCase):
    def setUp(self):
        self.store=Store()
        self.c=Coordinator(self.store,enabled=True)

    def tearDown(self):
        self.store.close()

    def submitted(self):
        x=collection()
        self.c.reserve(x, verified_company_id=A)
        self.c.authorize(x,mandate(),verified_company_id=A)
        self.c.submit_intent(company_id=A,operation_id=x.operation_id,
                             provider_id='VODACOM_TEST_ONLY',independent_approval=True)
        return x

    def test_disabled_does_not_write(self):
        with self.assertRaises(StateError):
            Coordinator(self.store).reserve(collection(),verified_company_id=A)
        self.assertEqual(self.store.conn.execute('SELECT count(*) FROM collections').fetchone()[0],0)

    def test_happy_path_nonposting(self):
        x=self.submitted()
        self.assertEqual(self.c.ingest(provider(),verified_company_id=A).status,'settled')
        result=self.c.propose_journal(company_id=A, operation_id=x.operation_id,
              verified_reconciliation=True,approved_policy=True,posting_key='post_TEST_12345678',
              allocations={'principal':Decimal('80.00'),'interest':Decimal('20.00')},
              account_map={'principal':'principal_receivable','interest':'interest_receivable'})
        self.assertEqual(result.status,'journal_proposed')
        rows=self.store.conn.execute('SELECT side,amount FROM journal_lines').fetchall()
        self.assertEqual(sum(Decimal(r['amount']) for r in rows if r['side']=='debit'),Decimal('100.00'))
        self.assertEqual(sum(Decimal(r['amount']) for r in rows if r['side']=='credit'),Decimal('100.00'))
        self.assertTrue(verify(self.store,company=str(A),operation=x.operation_id))
        self.assertEqual(self.store.conn.execute('SELECT count(*) FROM outbox').fetchone()[0],3)

    def test_repeated_request_same_state(self):
        x=collection(); self.c.reserve(x,verified_company_id=A)
        self.assertTrue(self.c.reserve(x,verified_company_id=A).repeated)
        self.assertEqual(self.store.conn.execute('SELECT count(*) FROM collections').fetchone()[0],1)

    def test_conflicting_key_rejected(self):
        x=collection(); self.c.reserve(x,verified_company_id=A)
        modified=replace(x,amount=Decimal('101.00'))
        with self.assertRaises(StateError): self.c.reserve(modified,verified_company_id=A)

    def test_idempotency_key_cannot_change_for_same_operation(self):
        x=collection(); self.c.reserve(x,verified_company_id=A)
        with self.assertRaises(StateError):
            self.c.reserve(replace(x,idempotency_key='idempotency_ANOTHER_123456'),verified_company_id=A)

    def test_tenant_isolation(self):
        x=collection(); self.c.reserve(x,verified_company_id=A)
        with self.assertRaises(StateError): self.c.reserve(x,verified_company_id=B)
        with self.assertRaises(StateError): self.c.timeout_unknown(company_id=B,operation_id=x.operation_id)
        other=collection(company=B)
        self.assertFalse(self.c.reserve(other,verified_company_id=B).repeated)

    def test_mandate_cross_company_rejected(self):
        x=collection(); self.c.reserve(x,verified_company_id=A)
        with self.assertRaises(StateError): self.c.authorize(x,mandate(company=B),verified_company_id=A)

    def test_mandate_undersized_rejected(self):
        x=collection(); self.c.reserve(x,verified_company_id=A)
        with self.assertRaises(StateError): self.c.authorize(x,mandate(limit='99.99'),verified_company_id=A)

    def test_unverified_mandate_rejected(self):
        with self.assertRaises(BoundaryError): replace(mandate(),verified=False)

    def test_submit_without_approval_rejected(self):
        x=collection();self.c.reserve(x,verified_company_id=A)
        self.c.authorize(x,mandate(),verified_company_id=A)
        with self.assertRaises(StateError):self.c.submit_intent(company_id=A,operation_id=x.operation_id,
                                                   provider_id='VODACOM_TEST_ONLY',independent_approval=False)

    def test_timeout_never_resubmits(self):
        x=self.submitted()
        self.c.timeout_unknown(company_id=A,operation_id=x.operation_id)
        with self.assertRaises(StateError):
            self.c.submit_intent(company_id=A,operation_id=x.operation_id,
                                 provider_id='VODACOM_TEST_ONLY',independent_approval=True)
        self.assertEqual(self.c.ingest(provider(),verified_company_id=A).status,'settled')

    def test_duplicate_provider_event_is_idempotent(self):
        self.submitted()
        self.c.ingest(provider(),verified_company_id=A)
        self.assertTrue(self.c.ingest(provider(),verified_company_id=A).repeated)
        self.assertEqual(self.store.conn.execute('SELECT count(*) FROM events').fetchone()[0],1)

    def test_duplicate_event_with_different_digest_rejected(self):
        self.submitted();self.c.ingest(provider(),verified_company_id=A)
        with self.assertRaises(StateError):
            self.c.ingest(provider(digest='b'*64),verified_company_id=A)

    def test_duplicate_event_across_operation_rejected(self):
        self.submitted();self.c.ingest(provider(),verified_company_id=A)
        with self.assertRaises(StateError):
            self.c.ingest(provider(operation='op_ANOTHER_12345678'),verified_company_id=A)

    def test_wrong_amount_rejected(self):
        self.submitted()
        with self.assertRaises(StateError):
            self.c.ingest(provider(amount='200.00'),verified_company_id=A)
        self.assertEqual(self.store.conn.execute('SELECT count(*) FROM events').fetchone()[0],0)

    def test_unverified_provider_rejected(self):
        with self.assertRaises(BoundaryError): replace(provider(),authenticated=False)

    def test_unexpected_settlement_from_reserved_rejected(self):
        x=collection();self.c.reserve(x,verified_company_id=A)
        with self.assertRaises(StateError):self.c.ingest(provider(),verified_company_id=A)

    def test_double_settlement_distinct_event_rejected(self):
        self.submitted();self.c.ingest(provider(),verified_company_id=A)
        with self.assertRaises(StateError):
            self.c.ingest(provider(event='evt_TEST_87654321'),verified_company_id=A)

    def test_wrong_provider_for_operation_rejected(self):
        self.submitted()
        with self.assertRaises(StateError):
            self.c.ingest(replace(provider(),provider_id='GOLINK_TEST_ONLY'),verified_company_id=A)
        self.assertEqual(self.store.conn.execute('SELECT count(*) FROM events').fetchone()[0],0)

    def test_provider_reference_change_rejected(self):
        x=self.submitted();self.c.ingest(provider(outcome='settled'),verified_company_id=A)
        self.c.request_reversal(company_id=A,operation_id=x.operation_id,independent_approval=True)
        with self.assertRaises(StateError):
            self.c.ingest(provider(outcome='reversed',event='evt_REVERSAL_12345',reference='another_ref_12345'),verified_company_id=A)

    def test_reversal_requires_independent_approval(self):
        x=self.submitted();self.c.ingest(provider(),verified_company_id=A)
        with self.assertRaises(StateError):
            self.c.request_reversal(company_id=A,operation_id=x.operation_id,independent_approval=False)
        self.c.request_reversal(company_id=A,operation_id=x.operation_id,independent_approval=True)
        self.assertEqual(self.c.ingest(provider(outcome='reversed',event='evt_REVERSE_12345'),verified_company_id=A).status,'reversed')

    def test_journal_requires_reconciliation(self):
        x=self.submitted();self.c.ingest(provider(),verified_company_id=A)
        with self.assertRaises(StateError):
            self.c.propose_journal(company_id=A,operation_id=x.operation_id,
              verified_reconciliation=False,approved_policy=True,posting_key='post_TEST_12345678',
              allocations={'principal':Decimal('100.00')},account_map={'principal':'principal_receivable'})

    def test_equal_and_opposite_reversal_proposal(self):
        x=self.submitted()
        self.c.ingest(provider(),verified_company_id=A)
        self.c.propose_journal(company_id=A,operation_id=x.operation_id,
            verified_reconciliation=True,approved_policy=True,posting_key='post_TEST_12345678',
            allocations={'principal':Decimal('80.00'),'interest':Decimal('20.00')},
            account_map={'principal':'principal_receivable','interest':'interest_receivable'})
        self.c.request_reversal(company_id=A,operation_id=x.operation_id,independent_approval=True)
        self.c.ingest(provider(outcome='reversed',event='evt_REVERSE_12345'),verified_company_id=A)
        self.c.propose_reversal_journal(company_id=A,operation_id=x.operation_id,
            posting_key='reverse_TEST_123456',independent_approval=True,
            verified_reversal_evidence=True)
        rows=self.store.conn.execute('SELECT kind,posting_key FROM journal').fetchall()
        self.assertEqual({r['kind'] for r in rows},{'settlement','reversal'})
        original=self.store.conn.execute('SELECT side,amount FROM journal_lines WHERE posting_key=?',('post_TEST_12345678',)).fetchall()
        reversal=self.store.conn.execute('SELECT side,amount FROM journal_lines WHERE posting_key=?',('reverse_TEST_123456',)).fetchall()
        self.assertEqual([(r['side'],r['amount']) for r in reversal],
            [('credit' if r['side']=='debit' else 'debit',r['amount']) for r in original])
        with self.assertRaises(StateError):
            self.c.propose_reversal_journal(company_id=A,operation_id=x.operation_id,
                 posting_key='another_rev_12345678',independent_approval=True,
                 verified_reversal_evidence=True)

    def test_reversal_journal_requires_existing_settlement_journal(self):
        x=self.submitted()
        self.c.ingest(provider(),verified_company_id=A)
        self.c.request_reversal(company_id=A,operation_id=x.operation_id,independent_approval=True)
        self.c.ingest(provider(outcome='reversed',event='evt_REVERSE_12345'),verified_company_id=A)
        with self.assertRaises(StateError):
            self.c.propose_reversal_journal(company_id=A,operation_id=x.operation_id,
                posting_key='reverse_TEST_123456',independent_approval=True,
                verified_reversal_evidence=True)

    def test_reversal_journal_requires_separate_approval(self):
        x=self.submitted()
        self.c.ingest(provider(),verified_company_id=A)
        self.c.propose_journal(company_id=A,operation_id=x.operation_id,
            verified_reconciliation=True,approved_policy=True,posting_key='post_TEST_12345678',
            allocations={'principal':Decimal('100.00')},account_map={'principal':'principal_receivable'})
        self.c.request_reversal(company_id=A,operation_id=x.operation_id,independent_approval=True)
        self.c.ingest(provider(outcome='reversed',event='evt_REVERSE_12345'),verified_company_id=A)
        with self.assertRaises(StateError):
            self.c.propose_reversal_journal(company_id=A,operation_id=x.operation_id,
                posting_key='reverse_TEST_123456',independent_approval=False,
                verified_reversal_evidence=True)

    def test_unbalanced_journal_rolls_back(self):
        x=self.submitted();self.c.ingest(provider(),verified_company_id=A)
        with self.assertRaises(StateError):
            self.c.propose_journal(company_id=A,operation_id=x.operation_id,
              verified_reconciliation=True,approved_policy=True,posting_key='post_TEST_12345678',
              allocations={'principal':Decimal('99.99')},account_map={'principal':'principal_receivable'})
        self.assertEqual(self.store.conn.execute('SELECT count(*) FROM journal').fetchone()[0],0)
        self.assertEqual(self.store.conn.execute('SELECT count(*) FROM outbox').fetchone()[0],2)

    def test_second_journal_rejected(self):
        x=self.submitted();self.c.ingest(provider(),verified_company_id=A)
        args=dict(company_id=A,operation_id=x.operation_id,verified_reconciliation=True,
                  approved_policy=True,posting_key='post_TEST_12345678',
                  allocations={'principal':Decimal('100.00')},account_map={'principal':'principal_receivable'})
        self.c.propose_journal(**args)
        with self.assertRaises(StateError):self.c.propose_journal(**args)

    def test_unknown_cannot_post(self):
        x=self.submitted();self.c.timeout_unknown(company_id=A,operation_id=x.operation_id)
        with self.assertRaises(StateError):
            self.c.propose_journal(company_id=A,operation_id=x.operation_id,
              verified_reconciliation=True,approved_policy=True,posting_key='post_TEST_12345678',
              allocations={'principal':Decimal('100.00')},account_map={'principal':'principal_receivable'})

    def test_outbox_five_failures_go_dead(self):
        self.submitted()
        message=self.store.conn.execute('SELECT id FROM outbox').fetchone()[0]
        for _ in range(4):self.c.acknowledge_outbox(outbox_id=message,accepted=False)
        self.c.acknowledge_outbox(outbox_id=message,accepted=False)
        self.assertEqual(self.store.conn.execute('SELECT state FROM outbox WHERE id=?',(message,)).fetchone()[0],'dead')
        with self.assertRaises(StateError): self.c.acknowledge_outbox(outbox_id=message,accepted=True)

    def test_outbox_success_once(self):
        self.submitted()
        message=self.store.conn.execute('SELECT id FROM outbox').fetchone()[0]
        self.c.acknowledge_outbox(outbox_id=message,accepted=True)
        with self.assertRaises(StateError):self.c.acknowledge_outbox(outbox_id=message,accepted=True)

    def test_audit_payload_tamper_detected(self):
        self.submitted()
        self.assertTrue(verify(self.store,company=str(A),operation='op_TEST_12345678'))
        self.store.conn.execute("UPDATE audit SET payload='{}' WHERE sequence=1")
        self.assertFalse(verify(self.store,company=str(A),operation='op_TEST_12345678'))

    def test_audit_chain_link_tamper_detected(self):
        self.submitted()
        self.store.conn.execute("UPDATE audit SET previous_hash='a' WHERE sequence=2")
        self.assertFalse(verify(self.store,company=str(A),operation='op_TEST_12345678'))

    def test_event_rollback_does_not_persist_partial_writes(self):
        self.submitted()
        self.store.conn.execute("CREATE TRIGGER prevent_audit BEFORE INSERT ON audit BEGIN SELECT RAISE(ABORT,'synthetic outage'); END")
        with self.assertRaises(sqlite3.IntegrityError):self.c.ingest(provider(),verified_company_id=A)
        self.assertEqual(self.store.conn.execute('SELECT count(*) FROM events').fetchone()[0],0)
        self.assertEqual(self.store.conn.execute("SELECT state FROM collections").fetchone()[0],'submitted')

    def test_company_key_partitioned(self):
        a=collection();b=collection(company=B)
        self.c.reserve(a,verified_company_id=A)
        self.c.reserve(b,verified_company_id=B)
        self.assertEqual(self.store.conn.execute('SELECT count(*) FROM collections').fetchone()[0],2)

    def test_bad_decimal_rejected(self):
        for amt in (Decimal('NaN'),Decimal('-1'),Decimal('100.001'),Decimal('0')):
            with self.subTest(amt=amt),self.assertRaises(BoundaryError):
                replace(collection(),amount=amt)

    def test_unauthorized_policy_accounts_rejected(self):
        x=self.submitted();self.c.ingest(provider(),verified_company_id=A)
        with self.assertRaises(StateError):
            self.c.propose_journal(company_id=A,operation_id=x.operation_id,
             verified_reconciliation=True,approved_policy=True,posting_key='post_TEST_12345678',
             allocations={'principal':Decimal('100.00')},account_map={'principal':'clearing_receivable'})

    def test_real_provider_never_invoked(self):
        self.submitted()
        rows=self.store.conn.execute('SELECT payload FROM outbox').fetchall()
        self.assertTrue(all('execution_enabled":false' in r['payload'] for r in rows))

if __name__=='__main__':unittest.main()
