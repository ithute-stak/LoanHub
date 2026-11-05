import argparse
import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

import bridge


class SyncTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.previous = bridge.HOME
        bridge.HOME = Path(self.temp.name)

    def tearDown(self):
        bridge.HOME = self.previous
        self.temp.cleanup()

    def prepare(self):
        source = bridge.HOME / "sample.capture"
        source.write_bytes(b"test-only-synthetic-pen-strokes")
        signer = str(uuid4())
        company = str(uuid4())
        args = argparse.Namespace(
            company_id=company, signer_kind="client",
            verified_signer_id=signer, phones="58123456 / 63123456",
            consent_reference="test-capture-only", capture_file=str(source),
        )
        with contextlib.redirect_stdout(io.StringIO()):
            bridge.register(args)
        return company

    def test_acknowledged_import_is_not_repeated(self):
        company = self.prepare()
        requests = []

        class Reply:
            status = 202
            def __init__(self, payload):
                self.payload = payload
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return False
            def read(self):
                return json.dumps({
                    "status": "pending_identity_review",
                    "source_record_id": self.payload["source_record_id"],
                }).encode()

        def fake_open(req, timeout):
            self.assertEqual(req.get_header("X-company-id"), company)
            self.assertTrue(req.full_url.startswith("https://"))
            payload = json.loads(req.data)
            requests.append(payload)
            return Reply(payload)

        args = argparse.Namespace(url="https://staging.example.com/api/v1/signature-bridge/imports")
        with patch.dict(os.environ, {"LOANHUB_SIGNATURE_BRIDGE_ACCESS_TOKEN": "staging-test-token"}), \
             patch.object(bridge.urllib.request, "urlopen", side_effect=fake_open):
            with contextlib.redirect_stdout(io.StringIO()):
                bridge.sync(args)
                bridge.sync(args)
        self.assertEqual(len(requests), 1)
        self.assertEqual(requests[0]["phone_numbers"], "26658123456/26663123456")
        with bridge.connection() as db:
            self.assertEqual(db.execute("SELECT status FROM sync_outbox").fetchone()[0], "acknowledged")

    def test_failed_connection_retains_queue(self):
        self.prepare()
        args = argparse.Namespace(url="https://staging.example.com/api/v1/signature-bridge/imports")
        with patch.dict(os.environ, {"LOANHUB_SIGNATURE_BRIDGE_ACCESS_TOKEN": "test-token"}), \
             patch.object(bridge.urllib.request, "urlopen", side_effect=OSError("disconnected")):
            with contextlib.redirect_stderr(io.StringIO()):
                bridge.sync(args)
        with bridge.connection() as db:
            self.assertEqual(db.execute("SELECT status, retry_count FROM sync_outbox").fetchone(),
                             ("queued", 1))

    def test_rejects_http_url(self):
        with patch.dict(os.environ, {"LOANHUB_SIGNATURE_BRIDGE_ACCESS_TOKEN": "token"}):
            with self.assertRaises(ValueError):
                bridge.sync(argparse.Namespace(url="http://localhost/api/v1/signature-bridge/imports"))


if __name__ == "__main__":
    unittest.main()
