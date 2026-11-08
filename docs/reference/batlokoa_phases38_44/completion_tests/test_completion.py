import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal as D
from hashlib import sha256
from uuid import UUID

from remaining_engine.contracts import TenantKey, Money, ContractError
from remaining_engine.transaction_integrity import Transaction, Status
from remaining_engine.ledger_posting import ApprovedAllocationPolicy, propose_settlement_journal, propose_full_reversal
from remaining_engine.reconciliation import Finding, Decision
from completion_engine.mandates import Mandate, MandateApproval,validate_mandate
from completion_engine.provider_registry import ProviderConfiguration,select_collection_provider,assert_preserves_direct_mpesa
from completion_engine.callback_intake import AuthenticatedCallback,verify_callback,deduplicate_callback
from completion_engine.financial_invariants import PostingAuthorization,assert_settlement_ready,assert_full_reversal
from completion_engine.recovery import RecoveryAction,classify_recovery
from completion_engine.fee_policy import CommercialTerms,quote_fees
from completion_engine.outbox_worker import OutboxLease,lease_for_delivery,record_delivery
from completion_engine.atomic_repository import stage_atomic_settlement
from completion_engine.provider_event_store import stage_provider_event

C=UUID('4236a21f-5164-48aa-90f3-a35eccd23ae2')
L=UUID('00000000-0000-4000-8000-000000000003')
B=UUID('00000000-0000-4000-8000-000000000004')
TENANT=TenantKey(C,L,B)
NOW=datetime(2026,11,8,tzinfo=timezone.utc)
OP='operation_12345678'
PROVIDER_TX='provider_tx_12345678'

def tx(status=Status.SETTLED):
    return Transaction(TENANT, Money(D('80.00')), OP, 'a'*64,
                       status=status,version=4,provider_reference=PROVIDER_TX)
def journal():
    policy=ApprovedAllocationPolicy('policy_12345678',
                  ('permitted_charges','interest','principal'),
                  (('principal','receivable_principal'),('interest','receivable_interest'),('permitted_charges','receivable_charges')),
                  'cash_clearing',True)
    return propose_settlement_journal(tenant=TENANT,operation_id=OP,
          posting_key='posting_12345678',payment=Money(D('80.00')),
          component_balances={'principal':D('100.00'),'interest':D('10.00'),
                              'permitted_charges':D('5.00')},policy=policy)
def auth():
    return PostingAuthorization(OP,'posting_12345678',OP,TENANT,True,'reviewer_12345678')
def callback(raw=b'{"status":"settled"}'):
    return AuthenticatedCallback('synthetic_test','callback_12345678',PROVIDER_TX,
        OP,TENANT,Money(D('80.00')),'settled',NOW,sha256(raw).hexdigest(),True)

class FakeVerifier:
    def __init__(self,event):self.event=event
    def verify(self,raw,headers,received_at):return self.event

class Row:
    def __init__(self,value):self.value=value
    def fetchone(self):return self.value
class FakeDB:
    def __init__(self,exists=False):self.queries=[];self.exists=exists
    def execute(self,sql,params):
        self.queries.append((sql,params))
        if sql.startswith('SELECT version'):return Row((4,'settled',D('80.00')))
        if sql.startswith('INSERT INTO phase42_journals'):
            return Row(None if self.exists else ('posting_12345678',))
        if sql.startswith('INSERT INTO phase42_provider_events'):
            return Row(None if self.exists else ('a'*64,))
        if sql.startswith('SELECT raw_digest'):
            return Row(('a'*64,OP,PROVIDER_TX,'settled',D('80.00')))
        return Row(None)
    def commit(self):raise AssertionError('The repository must never commit')

class CompletionTests(unittest.TestCase):
    def test_mandate_success(self):
        m=Mandate('mandate_12345678',TENANT,Money(D('100.00')),
          NOW-timedelta(days=1),NOW+timedelta(days=1),'a'*64,'verifier_12345678')
        p=MandateApproval(m.mandate_id,OP,Money(D('80.00')),True,'b'*64)
        self.assertIsNone(validate_mandate(m,p,tenant=TENANT,operation_id=OP,
                                           requested=Money(D('80.00')),at=NOW))
    def test_mandate_rejected_if_revoked(self):
        m=Mandate('mandate_12345678',TENANT,Money(D('100.00')),
          NOW-timedelta(days=1),NOW+timedelta(days=1),'a'*64,'verifier_12345678',True)
        p=MandateApproval(m.mandate_id,OP,Money(D('80.00')),True,'b'*64)
        with self.assertRaises(ContractError):
            validate_mandate(m,p,tenant=TENANT,operation_id=OP,requested=Money(D('80.00')),at=NOW)
    def test_mandate_rejected_when_amount_too_large(self):
        m=Mandate('mandate_12345678',TENANT,Money(D('70.00')),
          NOW-timedelta(days=1),NOW+timedelta(days=1),'a'*64,'verifier_12345678')
        p=MandateApproval(m.mandate_id,OP,Money(D('80.00')),True,'b'*64)
        with self.assertRaises(ContractError):
            validate_mandate(m,p,tenant=TENANT,operation_id=OP,requested=Money(D('80.00')),at=NOW)
    def test_mandate_rejected_if_not_verified(self):
        m=Mandate('mandate_12345678',TENANT,Money(D('100.00')),
          NOW-timedelta(days=1),NOW+timedelta(days=1),'a'*64,'verifier_12345678')
        p=MandateApproval(m.mandate_id,OP,Money(D('80.00')),False,'b'*64)
        with self.assertRaises(ContractError):
            validate_mandate(m,p,tenant=TENANT,operation_id=OP,requested=Money(D('80.00')),at=NOW)
    def test_provider_registry_keeps_direct_mpesa(self):
        p=ProviderConfiguration('direct_mpesa','direct_adapter',True,False,True,True,True,True)
        self.assertEqual(select_collection_provider(p),'direct_adapter')
        self.assertIsNone(assert_preserves_direct_mpesa({'direct_mpesa':p}))
    def test_provider_registry_rejects_live(self):
        p=ProviderConfiguration('direct_mpesa','direct_adapter',True,False,True,True,True,True)
        with self.assertRaises(ContractError):select_collection_provider(p,live=True)
    def test_provider_registry_rejects_golink_replacement(self):
        with self.assertRaises(ContractError):assert_preserves_direct_mpesa({'golink':None})
    def test_provider_registry_rejects_no_merchant_authorization(self):
        p=ProviderConfiguration('direct_mpesa','direct_adapter',True,False,True,True,True,False)
        with self.assertRaises(ContractError):select_collection_provider(p)
    def test_authenticated_callback(self):
        raw=b'{"status":"settled"}'
        self.assertEqual(verify_callback(verifier=FakeVerifier(callback(raw)),raw=raw,
             headers={},received_at=NOW,expected_provider='synthetic_test').event_id,'callback_12345678')
    def test_callback_rejects_changed_body(self):
        with self.assertRaises(ContractError):
            verify_callback(verifier=FakeVerifier(callback()),raw=b'changed',
             headers={},received_at=NOW,expected_provider='synthetic_test')
    def test_callback_rejects_unverified(self):
        with self.assertRaises(ContractError):
            verify_callback(verifier=FakeVerifier(replace(callback(),authenticated=False)),
                  raw=b'{"status":"settled"}',headers={},received_at=NOW,expected_provider='synthetic_test')
    def test_callback_rejects_wrong_provider(self):
        with self.assertRaises(ContractError):
            verify_callback(verifier=FakeVerifier(callback()),raw=b'{"status":"settled"}',
                  headers={},received_at=NOW,expected_provider='wrong')
    def test_callback_rejects_large_payload(self):
        with self.assertRaises(ContractError):
            verify_callback(verifier=FakeVerifier(callback()),raw=b'x'*65537,
                   headers={},received_at=NOW,expected_provider='synthetic_test')
    def test_callback_replay(self):
        self.assertEqual(deduplicate_callback('a'*64,'a'*64),'replay')
        self.assertEqual(deduplicate_callback('a'*64,'b'*64),'conflict')
        self.assertEqual(deduplicate_callback(None,'b'*64),'new')
    def test_settlement_posting_invariants(self):
        assert_settlement_ready(transaction=tx(),journal=journal(),
            finding=Finding(OP,Decision.MATCHED,False),authorization=auth())
    def test_posting_rejects_unsettled(self):
        with self.assertRaises(ContractError):assert_settlement_ready(
            transaction=tx(Status.UNKNOWN),journal=journal(),finding=Finding(OP,Decision.MATCHED,False),authorization=auth())
    def test_posting_rejects_mismatch(self):
        with self.assertRaises(ContractError):assert_settlement_ready(
            transaction=tx(),journal=journal(),finding=Finding(OP,Decision.AMOUNT_MISMATCH,True),authorization=auth())
    def test_reversal_invariant(self):
        j=journal();assert_full_reversal(j,propose_full_reversal(j,reversal_key='reversal_12345678'))
    def test_recovery_unknown_never_resubmits(self):
        self.assertEqual(classify_recovery(tx(Status.UNKNOWN),provider_status_authenticated=False,
                        reconciled=False,operator_approved=False),RecoveryAction.INVESTIGATE_PROVIDER)
    def test_recovery_settled_reconciles(self):
        self.assertEqual(classify_recovery(tx(),provider_status_authenticated=True,
                          reconciled=False,operator_approved=False),RecoveryAction.RECONCILE)
    def test_fee_quote_never_invents_provider_fee(self):
        terms=CommercialTerms('agreement_12345678',str(C),'collection',D('2.00'),100,D('10.00'),True,'provider_contract')
        result=quote_fees(Money(D('100.00')),terms)
        self.assertEqual(result.platform_fee.value,D('3.00'))
        self.assertIsNone(result.provider_fee)
        self.assertIsNone(result.total_customer_debit)
    def test_fee_quote_rejects_unapproved(self):
        terms=CommercialTerms('agreement_12345678',str(C),'collection',D('2.00'),100,D('10.00'),False,'provider_contract')
        with self.assertRaises(ContractError):quote_fees(Money(D('100.00')),terms)
    def test_outbox_lease_and_retry(self):
        item=OutboxLease('event_12345678',0,NOW,None,'pending')
        lease=lease_for_delivery(item,now=NOW)
        self.assertEqual(lease.attempts,1)
        self.assertEqual(record_delivery(lease,ack=False,now=NOW).status,'pending')
        self.assertEqual(record_delivery(lease,ack=True,now=NOW).status,'delivered')
    def test_outbox_double_claim_rejected(self):
        lease=lease_for_delivery(OutboxLease('event_12345678',0,NOW,None,'pending'),now=NOW)
        with self.assertRaises(ContractError):lease_for_delivery(lease,now=NOW)
    def test_db_posting_disabled_before_reads(self):
        db=FakeDB()
        with self.assertRaises(ContractError):stage_atomic_settlement(db=db,transaction=tx(),
            journal=journal(),finding=Finding(OP,Decision.MATCHED,False),approval=auth())
        self.assertEqual(db.queries,[])
    def test_db_posting_stages_balanced_lines_event_outbox(self):
        db=FakeDB()
        outcome=stage_atomic_settlement(db=db,transaction=tx(),journal=journal(),
            finding=Finding(OP,Decision.MATCHED,False),approval=auth(),enabled=True)
        self.assertTrue(outcome.staged)
        self.assertEqual(len(db.queries),len(journal().lines)+4)
    def test_db_posting_rejects_duplicate_without_extra_writes(self):
        db=FakeDB(exists=True)
        with self.assertRaises(ContractError):stage_atomic_settlement(db=db,transaction=tx(),
            journal=journal(),finding=Finding(OP,Decision.MATCHED,False),approval=auth(),enabled=True)
        self.assertEqual(len(db.queries),2)
    def test_provider_event_disabled_before_write(self):
        db=FakeDB()
        with self.assertRaises(ContractError):stage_provider_event(db,callback(),verified_company_id=C)
        self.assertEqual(db.queries,[])
    def test_provider_event_created_and_replayed(self):
        self.assertEqual(stage_provider_event(FakeDB(),callback(),verified_company_id=C,enabled=True),'created')
        # callback(raw) digest differs from the canned hash 'a'*64, so conflicting reuse must reject
        with self.assertRaises(ContractError):stage_provider_event(FakeDB(exists=True),callback(),verified_company_id=C,enabled=True)
    def test_provider_event_wrong_tenant(self):
        db=FakeDB()
        with self.assertRaises(ContractError):stage_provider_event(db,callback(),verified_company_id=L,enabled=True)
        self.assertEqual(db.queries,[])

if __name__=='__main__':unittest.main()
