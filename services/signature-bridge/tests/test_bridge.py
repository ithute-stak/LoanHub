import argparse
import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path

import bridge

class BridgeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old = bridge.HOME
        bridge.HOME = Path(self.tmp.name)
    def tearDown(self):
        bridge.HOME = self.old
        self.tmp.cleanup()
    def test_phone_normalization(self):
        self.assertEqual(bridge.split_phones("58123456 / +26663123456 / 58123456"),
                         ["26658123456", "26663123456"])
        with self.assertRaises(ValueError):
            bridge.split_phones("58123456/")
    def capture(self, name, phones):
        path = bridge.HOME / (name + ".capture")
        path.write_bytes(b"synthetic-pen-data-not-a-signature")
        args = argparse.Namespace(company_id="tenant-A", signer_kind="client",
            verified_signer_id=name, phones=phones, consent_reference="test-consent",
            capture_file=str(path))
        with contextlib.redirect_stdout(io.StringIO()):
            bridge.register(args)
    def resolve(self, phones, tenant="tenant-A"):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            bridge.resolve(argparse.Namespace(company_id=tenant, signer_kind="client",
                            verified_signer_id=None, phones=phones))
        return json.loads(buf.getvalue())
    def test_match_and_tenant_isolation(self):
        self.capture("person1", "58123456 / 63123456")
        self.assertEqual(self.resolve("63123456")["status"], "match")
        self.assertFalse(self.resolve("58123456")["auto_apply"])
        self.assertEqual(self.resolve("58123456", "tenant-B")["status"], "not_found")
    def test_conflict(self):
        self.capture("person1", "58123456")
        self.capture("person2", "63123456")
        result = self.resolve("58123456 / 63123456")
        self.assertEqual(result["status"], "conflict")
        self.assertEqual(result["signature_ids"], [])
    def test_multiple_signatures_same_signer_conflict(self):
        self.capture("person1", "58123456")
        self.capture("person1", "58123456")
        self.assertEqual(self.resolve("58123456")["status"], "conflict")

if __name__ == "__main__":
    unittest.main()
