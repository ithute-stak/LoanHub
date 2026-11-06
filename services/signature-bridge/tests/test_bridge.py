import argparse
import contextlib
import io
import json
import os
import tempfile
import unittest
from unittest.mock import patch
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
    def test_connection_closes_after_context(self):
        with bridge.connection() as db:
            self.assertEqual(db.execute("SELECT 1").fetchone()[0], 1)
        with self.assertRaises(bridge.sqlite3.ProgrammingError):
            db.execute("SELECT 1")

    def test_redacted_local_queue_audit(self):
        args = argparse.Namespace(
            company_id="synthetic-tenant", signer_kind="officer",
            verified_signer_id="synthetic-officer", phones="",
            consent_reference="DISPOSABLE-LOCAL-HARDWARE-TEST",
            capture_file=str(bridge.HOME / "synthetic.capture"),
        )
        Path(args.capture_file).write_bytes(b"secret-synthetic-stroke-data")
        with contextlib.redirect_stdout(io.StringIO()):
            bridge.register(args)
        output = io.StringIO()
        with unittest.mock.patch.dict(os.environ, {"LOANHUB_SIGNATURE_BRIDGE_MODE": "staging"}):
            with contextlib.redirect_stdout(output):
                bridge.audit_local_queue(argparse.Namespace())
        payload = json.loads(output.getvalue())
        self.assertFalse(payload["remote_sync_enabled"])
        self.assertEqual(len(payload["records"]), 1)
        record = payload["records"][0]
        self.assertTrue(record["disposable_test_reference"])
        self.assertFalse(record["identity_independently_verified"])
        self.assertNotIn("secret-synthetic-stroke-data", output.getvalue())
        self.assertNotIn("synthetic-officer", output.getvalue())
        self.assertNotIn("synthetic-tenant", output.getvalue())

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
