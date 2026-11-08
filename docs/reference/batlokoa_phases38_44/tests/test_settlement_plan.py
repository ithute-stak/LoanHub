import unittest
from dataclasses import replace
from decimal import Decimal as D
from uuid import UUID
from remaining_engine.contracts import TenantKey,Money,ContractError
from remaining_engine.transaction_integrity import Transaction,Status
from remaining_engine.reconciliation import Finding,Decision
from remaining_engine.ledger_posting import ApprovedAllocationPolicy
from remaining_engine.settlement_plan import propose_posting
T=TenantKey(UUID('00000000-0000-4000-8000-000000000001'),UUID('00000000-0000-4000-8000-000000000002'),UUID('00000000-0000-4000-8000-000000000003'))
TX=Transaction(T,Money(D('50.00')),'operation_test_1234','a'*64,Status.SETTLED,3)
F=Finding(TX.operation_id,Decision.MATCHED,False)
P=ApprovedAllocationPolicy('policy_test_1234',('principal','interest','permitted_charges'),
 (('principal','PR'),('interest','IN'),('permitted_charges','CH')),'CLEAR',True)
BAL={'principal':D('100.00'),'interest':D('5.00'),'permitted_charges':D('5.00')}
def plan(**kwargs):
    opts=dict(transaction=TX,finding=F,component_balances=BAL,approved_policy=P,unique_posting_key='posting_test_1234')
    opts.update(kwargs)
    return propose_posting(**opts)
class TestPlan(unittest.TestCase):
    def test_matched_settlement_proposes_balanced_journal(self):
        p=plan();self.assertTrue(p.requires_database_lock);self.assertTrue(p.requires_unique_posting_key)
    def test_no_posting_for_unknown(self):
        with self.assertRaises(ContractError):plan(transaction=replace(TX,status=Status.UNKNOWN))
    def test_no_posting_for_reserved(self):
        with self.assertRaises(ContractError):plan(transaction=replace(TX,status=Status.RESERVED))
    def test_no_posting_for_unreconciled(self):
        with self.assertRaises(ContractError):plan(finding=replace(F,decision=Decision.AMOUNT_MISMATCH))
    def test_no_posting_for_other_operation(self):
        with self.assertRaises(ContractError):plan(finding=replace(F,operation_id='different_test_1234'))
