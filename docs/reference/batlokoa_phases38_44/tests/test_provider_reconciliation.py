import unittest
from dataclasses import replace
from decimal import Decimal as D
from uuid import UUID
from remaining_engine.contracts import TenantKey,Money,ContractError
from remaining_engine.provider_boundary import ProviderCapabilities,EvidenceEnvelope,accept_verified_evidence,assert_live_provider_certified
from remaining_engine.reconciliation import Record,Decision,reconcile
T=TenantKey(UUID('00000000-0000-4000-8000-000000000001'),UUID('00000000-0000-4000-8000-000000000002'),UUID('00000000-0000-4000-8000-000000000003'))
class Adapter:
    capabilities=ProviderCapabilities('TEST_ONLY',True,False,True,False)
E=EvidenceEnvelope('TEST_ONLY','event_test_1234','operation_test_1234','settled',Money(D('100.00')),T,'provider_test_1234',True)
R=Record(T,'operation_test_1234','provider_test_1234',Money(D('100.00')),'TEST_ONLY','settled')
class TestProviderAndReconcile(unittest.TestCase):
    def test_accepted_test_evidence(self):self.assertTrue(accept_verified_evidence(adapter=Adapter(),envelope=E,expected_tenant=T,expected_operation=E.operation_id,expected_money=E.amount).verified)
    def test_no_live_certification(self):
        with self.assertRaises(ContractError):assert_live_provider_certified(Adapter())
    def test_unverified_evidence(self):
        with self.assertRaises(ContractError):accept_verified_evidence(adapter=Adapter(),envelope=replace(E,verified_by_adapter=False),expected_tenant=T,expected_operation=E.operation_id,expected_money=E.amount)
    def test_wrong_tenant(self):
        other=TenantKey(UUID('00000000-0000-4000-8000-000000000099'),T.loan_id,T.borrower_id)
        with self.assertRaises(ContractError):accept_verified_evidence(adapter=Adapter(),envelope=replace(E,tenant=other),expected_tenant=T,expected_operation=E.operation_id,expected_money=E.amount)
    def test_wrong_amount(self):
        with self.assertRaises(ContractError):accept_verified_evidence(adapter=Adapter(),envelope=E,expected_tenant=T,expected_operation=E.operation_id,expected_money=Money(D('101.00')))
    def test_matched(self):self.assertEqual(reconcile((R,),(R,))[0].decision,Decision.MATCHED)
    def test_duplicate_provider(self):self.assertEqual(reconcile((R,),(R,R))[0].decision,Decision.DUPLICATE_PROVIDER)
    def test_duplicate_internal(self):self.assertEqual(reconcile((R,R),(R,))[0].decision,Decision.DUPLICATE_INTERNAL)
    def test_missing_provider(self):self.assertEqual(reconcile((R,),())[0].decision,Decision.MISSING_PROVIDER)
    def test_missing_internal(self):self.assertEqual(reconcile((),(R,))[0].decision,Decision.MISSING_INTERNAL)
    def test_amount_mismatch(self):self.assertEqual(reconcile((R,),(replace(R,money=Money(D('99.00'))),))[0].decision,Decision.AMOUNT_MISMATCH)
    def test_unknown(self):self.assertEqual(reconcile((replace(R,status='unknown'),),(R,))[0].decision,Decision.UNKNOWN_OUTCOME)
    def test_reference_conflict(self):self.assertEqual(reconcile((R,),(replace(R,provider_reference='different_ref_1234'),))[0].decision,Decision.PROVIDER_MISMATCH)
    def test_tenant_conflict(self):
        other=TenantKey(UUID('00000000-0000-4000-8000-000000000099'),T.loan_id,T.borrower_id)
        self.assertEqual(reconcile((R,),(replace(R,tenant=other),))[0].decision,Decision.TENANT_MISMATCH)
