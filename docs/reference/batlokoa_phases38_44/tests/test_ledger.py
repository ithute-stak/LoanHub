import unittest
from decimal import Decimal as D
from uuid import UUID
from dataclasses import replace
from remaining_engine.contracts import TenantKey, Money, ContractError
from remaining_engine.ledger_posting import (ApprovedAllocationPolicy,propose_settlement_journal,
    propose_full_reversal,validate_balanced,Line)
TENANT=TenantKey(UUID('00000000-0000-4000-8000-000000000001'),UUID('00000000-0000-4000-8000-000000000002'),UUID('00000000-0000-4000-8000-000000000003'))
P=ApprovedAllocationPolicy('policy_test_1234',('permitted_charges','interest','principal'),
    (('principal','PR'),('interest','IN'),('permitted_charges','CH')),'CLEAR',True)
BAL={'principal':D('100.00'),'interest':D('20.00'),'permitted_charges':D('5.00')}
def journal():return propose_settlement_journal(tenant=TENANT,operation_id='operation_test_1234',posting_key='posting_test_1234',payment=Money(D('85.00')),component_balances=BAL,policy=P)
class TestLedger(unittest.TestCase):
    def test_balanced(self):
        j=journal();self.assertEqual(sum((x.amount.value for x in j.lines if x.side=='credit'),D('0')),D('85.00'))
        self.assertEqual(len(j.lines),4)
    def test_exact_allocation(self):
        j=journal(); self.assertEqual({x.account:x.amount.value for x in j.lines}['PR'],D('60.00'))
    def test_zero_skip(self):
        j=propose_settlement_journal(tenant=TENANT,operation_id='operation_test_1234',posting_key='posting_test_1234',payment=Money(D('5.00')),component_balances=BAL,policy=P)
        self.assertEqual(len(j.lines),2)
    def test_overpayment(self):
        with self.assertRaises(ContractError):propose_settlement_journal(tenant=TENANT,operation_id='operation_test_1234',posting_key='posting_test_1234',payment=Money(D('126.00')),component_balances=BAL,policy=P)
    def test_missing_component(self):
        with self.assertRaises(ContractError):propose_settlement_journal(tenant=TENANT,operation_id='operation_test_1234',posting_key='posting_test_1234',payment=Money(D('50.00')),component_balances={'principal':D('100')},policy=P)
    def test_reversal_balances(self):
        j=journal();rev=propose_full_reversal(j,reversal_key='reversal_test_1234');validate_balanced(rev)
        self.assertEqual(rev.lines[0].side,'credit')
    def test_reversal_key_unique(self):
        with self.assertRaises(ContractError):propose_full_reversal(journal(),reversal_key='posting_test_1234')
    def test_unapproved_policy(self):
        with self.assertRaises(ContractError):replace(P,approved=False)
    def test_wrong_accounts(self):
        with self.assertRaises(ContractError):replace(P,clearing_account='PR')
    def test_forged_ledger(self):
        j=journal();wrong=replace(j,lines=j.lines[:1]);
        with self.assertRaises(ContractError):validate_balanced(wrong)
