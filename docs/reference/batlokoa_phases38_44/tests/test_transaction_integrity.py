import unittest
from dataclasses import replace
from decimal import Decimal
from uuid import UUID
from remaining_engine.contracts import TenantKey, Money
from remaining_engine.transaction_integrity import (Transaction, Command, Status, VerifiedMandate,
    VerifiedProviderResult, TransitionError, transition)
T=TenantKey(UUID('00000000-0000-4000-8000-000000000001'),UUID('00000000-0000-4000-8000-000000000002'),UUID('00000000-0000-4000-8000-000000000003'))
M=Money(Decimal('100.00'))
O=Transaction(T,M,'operation_test_1234','a'*64)
def mandate(approved=True):return VerifiedMandate(T,O.operation_id,M,'mandate_test_1234',approved)
def provider(outcome='settled',money=M):return VerifiedProviderResult(T,O.operation_id,money,'provider_ref_1234','provider_evt_1234',outcome,True)
def ready():
    tx=transition(O,Command.VERIFY_MANDATE,expected_version=0,mandate=mandate())
    return transition(tx,Command.SUBMIT,expected_version=1)
class TestState(unittest.TestCase):
    def test_valid_submit(self):self.assertEqual(ready().status,Status.SUBMITTED)
    def test_mandate_missing(self):
        with self.assertRaises(TransitionError):transition(O,Command.VERIFY_MANDATE,expected_version=0)
    def test_mandate_rejected(self):
        with self.assertRaises(TransitionError):transition(O,Command.VERIFY_MANDATE,expected_version=0,mandate=mandate(False))
    def test_stale_version(self):
        with self.assertRaises(TransitionError):transition(O,Command.VERIFY_MANDATE,expected_version=1,mandate=mandate())
    def test_no_early_submit(self):
        with self.assertRaises(TransitionError):transition(O,Command.SUBMIT,expected_version=0)
    def test_settlement(self):
        settled=transition(ready(),Command.PROVIDER_SETTLEMENT,expected_version=2,provider=provider())
        self.assertEqual((settled.status,settled.version),(Status.SETTLED,3))
    def test_no_double_settle(self):
        settled=transition(ready(),Command.PROVIDER_SETTLEMENT,expected_version=2,provider=provider())
        with self.assertRaises(TransitionError):transition(settled,Command.PROVIDER_SETTLEMENT,expected_version=3,provider=provider())
    def test_unknown_cannot_resubmit(self):
        tx=transition(ready(),Command.TIMEOUT,expected_version=2)
        with self.assertRaises(TransitionError):transition(tx,Command.SUBMIT,expected_version=3)
    def test_unknown_can_settle_with_evidence(self):
        tx=transition(ready(),Command.TIMEOUT,expected_version=2)
        self.assertEqual(transition(tx,Command.PROVIDER_SETTLEMENT,expected_version=3,provider=provider()).status,Status.SETTLED)
    def test_wrong_amount_provider(self):
        with self.assertRaises(TransitionError):transition(ready(),Command.PROVIDER_SETTLEMENT,expected_version=2,provider=provider(money=Money(Decimal('90.00'))))
    def test_wrong_outcome(self):
        with self.assertRaises(TransitionError):transition(ready(),Command.PROVIDER_SETTLEMENT,expected_version=2,provider=provider('failed'))
    def test_reversal_requires_approval(self):
        settled=transition(ready(),Command.PROVIDER_SETTLEMENT,expected_version=2,provider=provider())
        with self.assertRaises(TransitionError):transition(settled,Command.REQUEST_REVERSAL,expected_version=3)
        requested=transition(settled,Command.REQUEST_REVERSAL,expected_version=3,independent_reversal_approval=True)
        done=transition(requested,Command.PROVIDER_REVERSAL,expected_version=4,provider=provider('reversed'))
        self.assertEqual(done.status,Status.REVERSED)
    def test_no_provider_forgery(self):
        with self.assertRaises(TransitionError):transition(ready(),Command.PROVIDER_SETTLEMENT,expected_version=2,provider=replace(provider(),verified=False))
