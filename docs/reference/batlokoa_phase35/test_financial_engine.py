"""Offline pure-domain financial-engine regression checks."""
from decimal import Decimal as D
import hashlib
import hmac
import json
import unittest
from financial_allocation import AllocationError, propose_allocation
from double_entry import JournalError, Journal, Line, validate_journal, propose_received_collection_journal
from provider_evidence import EvidenceError, verify_test_provider_evidence
from reconciliation import PaymentRecord, MatchStatus, reconcile

class FinancialContractTests(unittest.TestCase):
    def allocation(self, amount="85.00", order=("permitted_charges", "interest", "principal")):
        return propose_allocation(
            amount=D(amount),
            balances={"permitted_charges": D("5.00"), "interest": D("20.00"), "principal": D("100.00")},
            approved_order=order, policy_version="Batlokoa-review-v1",
        )

    def test_allocation(self):
        result = self.allocation()
        self.assertEqual(result.allocated["principal"], D("60.00"))
        self.assertEqual(result.allocated_total, D("85.00"))

    def test_order_changes_result(self):
        result = self.allocation(order=("principal", "interest", "permitted_charges"))
        self.assertEqual(result.allocated["principal"], D("85.00"))

    def test_overpayment_rejected(self):
        with self.assertRaises(AllocationError):
            self.allocation("125.01")

    def test_invalid_values_fail(self):
        for value in ("-1", "NaN", "1.001", "Infinity", "0"):
            with self.subTest(value=value), self.assertRaises(AllocationError):
                self.allocation(value)

    def test_balanced_journal(self):
        journal = propose_received_collection_journal(
            allocation=self.allocation(), reference="proof_12345678",
            clearing_account="clearing",
            receivable_accounts={
                "principal": "principal_receivable", "interest": "interest_receivable",
                "permitted_charges": "charge_receivable",
            },
        )
        self.assertEqual(sum(x.debit for x in journal.lines), D("85.00"))
        self.assertEqual(sum(x.credit for x in journal.lines), D("85.00"))

    def test_unbalanced_journal_rejected(self):
        with self.assertRaises(JournalError):
            validate_journal(Journal("ref", "LSL", (
                Line("A", D("10.00"), D("0.00")),
                Line("B", D("1.00"), D("0.00")),
            )))

    def test_signed_evidence_vector(self):
        key = b"offline-reference-only-secret-12345678"
        raw = json.dumps({
            "provider": "TEST_PROVIDER", "event_id": "evt_12345678",
            "operation_id": "op_123456789", "kind": "settled",
            "amount": "85.00", "currency": "LSL",
        }, sort_keys=True, separators=(",", ":")).encode()
        signature = hmac.new(key, raw, hashlib.sha256).hexdigest()
        evidence = verify_test_provider_evidence(raw_body=raw,
            supplied_signature=signature, shared_test_key=key, expected_provider="TEST_PROVIDER")
        self.assertEqual(evidence.amount, "85.00")
        with self.assertRaises(EvidenceError):
            verify_test_provider_evidence(raw_body=raw.replace(b"85.00", b"95.00"),
                supplied_signature=signature, shared_test_key=key, expected_provider="TEST_PROVIDER")

    def test_duplicate_settlement_never_matches(self):
        results = reconcile(
            internal=(PaymentRecord("ref", D("10.00")),),
            provider=(PaymentRecord("ref", D("10.00")), PaymentRecord("ref", D("10.00"))),
        )
        self.assertEqual(results[0].status, MatchStatus.DUPLICATE_PROVIDER)

    def test_currency_mismatch(self):
        results = reconcile(internal=(PaymentRecord("ref", D("10.00")),),
            provider=(PaymentRecord("ref", D("10.00"), "USD"),))
        self.assertEqual(results[0].status, MatchStatus.CURRENCY_MISMATCH)

if __name__ == "__main__":
    unittest.main()
