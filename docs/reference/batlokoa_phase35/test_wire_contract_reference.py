"""No network, production service, or secrets accessed."""
from dataclasses import replace
import unittest
from wire_contract_reference import signed_test_vector, verify_test_vector

PARAMS = dict(secret="offline-test-key-not-for-production-0123456789",
              timestamp=1794024000, nonce="offline_nonce_A123456789012345",
              amount="100.00", source_reference="loan_ref_A1234567",
              idempotency_key="collect_req_A123456789")

class ContractTests(unittest.TestCase):
    def test_valid_signature(self):
        vector = signed_test_vector(**PARAMS)
        self.assertTrue(verify_test_vector(vector, secret=PARAMS["secret"]))

    def test_modified_amount_detected(self):
        vector = signed_test_vector(**PARAMS)
        altered = replace(vector, body=vector.body.replace(b"100.00", b"100.01"))
        self.assertFalse(verify_test_vector(altered, secret=PARAMS["secret"]))

    def test_changed_key_or_source_changes_signature(self):
        original = signed_test_vector(**PARAMS)
        changed = signed_test_vector(**{**PARAMS, "idempotency_key":"collect_req_B123456789"})
        self.assertNotEqual(original.headers["X-LoanHub-Signature"],
                            changed.headers["X-LoanHub-Signature"])

    def test_invalid_amounts(self):
        for amount in ("0", "-1", "1.001", "NaN", "Infinity"):
            with self.subTest(amount=amount), self.assertRaises(ValueError):
                signed_test_vector(**{**PARAMS, "amount": amount})

if __name__ == "__main__":
    unittest.main()
