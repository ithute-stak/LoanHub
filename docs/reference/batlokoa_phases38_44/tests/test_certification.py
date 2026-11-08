import unittest
from remaining_engine.certification import Gate,REQUIRED,assess
from remaining_engine.contracts import ContractError
class TestCertification(unittest.TestCase):
    def test_missing_gates(self):self.assertFalse(assess(()).ready_for_review)
    def test_all_evidence(self):
        report=assess(tuple(Gate(name,True,'review_record_123') for name in REQUIRED))
        self.assertTrue(report.ready_for_review)
    def test_missing_evidence_fails(self):
        vals=tuple(Gate(name,True,'' if name=='signed_webhooks' else 'review_record_123') for name in REQUIRED)
        self.assertIn('signed_webhooks',assess(vals).failed)
    def test_failed_gate(self):
        vals=tuple(Gate(name,name!='rollback_drill','review_record_123') for name in REQUIRED)
        self.assertIn('rollback_drill',assess(vals).failed)
    def test_duplicates(self):
        with self.assertRaises(ContractError):assess((Gate('postgres_rls',True,'a'),Gate('postgres_rls',True,'b')))
    def test_unknown(self):
        with self.assertRaises(ContractError):assess((Gate('invented',True,'a'),))
