import unittest
from dataclasses import replace
from uuid import UUID
from remaining_engine.contracts import TenantKey, ContractError
from remaining_engine.audit_outbox import Event,digest,verify_chain,propose_outbox
T=TenantKey(UUID('00000000-0000-4000-8000-000000000001'),UUID('00000000-0000-4000-8000-000000000002'),UUID('00000000-0000-4000-8000-000000000003'))
def chain():
    a=Event(T,'operation_test_1234',UUID('00000000-0000-4000-8000-000000000004'),1,'created','a'*64,None)
    b=Event(T,'operation_test_1234',UUID('00000000-0000-4000-8000-000000000005'),2,'submitted','b'*64,digest(a))
    return a,b
class TestAudit(unittest.TestCase):
    def test_chain(self):
        v=chain();self.assertTrue(verify_chain(v,expected_tip=digest(v[-1])))
    def test_modified_tip(self):
        v=chain();self.assertFalse(verify_chain(v,expected_tip='f'*64))
    def test_modified_payload(self):
        v=chain();self.assertFalse(verify_chain((v[0],replace(v[1],payload_digest='c'*64)),expected_tip=digest(v[-1])))
    def test_missing_event(self):
        v=chain();
        with self.assertRaises(ContractError):verify_chain((v[1],),expected_tip=digest(v[-1]))
    def test_tenant_leak(self):
        v=chain();other=TenantKey(UUID('00000000-0000-4000-8000-000000000099'),T.loan_id,T.borrower_id)
        with self.assertRaises(ContractError):verify_chain((v[0],replace(v[1],tenant=other)),expected_tip=digest(v[-1]))
    def test_duplicate_sequence(self):
        v=chain();
        with self.assertRaises(ContractError):verify_chain((v[0],replace(v[1],version=1,previous_digest=None)),expected_tip=digest(v[-1]))
    def test_outbox(self):
        v=chain();m=propose_outbox(v[-1]);self.assertEqual(m.event_digest,digest(v[-1]))
    def test_genesis_no_outbox(self):
        with self.assertRaises(ContractError):propose_outbox(chain()[0])
