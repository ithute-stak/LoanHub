"""Integration: synthetic SDK output -> encrypted queue -> HTTPS acknowledgement.

Does not claim actual Wacom hardware access or authenticate customer consent.
"""
import argparse
import contextlib
import hashlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

import bridge
from cryptography.fernet import Fernet


class FullOfflineFlowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old_home = bridge.HOME
        bridge.HOME = Path(self.tmp.name) / "data"
        self.adapter = Path(self.tmp.name) / "synthetic-sdk"
        self.adapter.write_text("#!/bin/sh\nexit 0\n")
        self.adapter.chmod(0o700)
        self.capture = json.dumps({
            "format": "loanhub-pen-strokes-v1",
            "strokes": [[
                {"x": .12, "y": .43, "pressure": .61, "t": 1},
                {"x": .22, "y": .48, "pressure": .75, "t": 9},
            ]],
        }).encode()
        self.actor = argparse.Namespace(
            sdk_adapter=str(self.adapter), company_id=str(uuid4()),
            signer_kind="client", verified_signer_id=str(uuid4()),
            phones="58123456 / 63123456",
            consent_reference="simulated-review-reference",
            consent_confirmed=True, identity_verified=True,
        )
        self.url = "https://staging.example.invalid/api/v1/signature-bridge/imports"

    def tearDown(self):
        bridge.HOME = self.old_home
        self.tmp.cleanup()

    def _capture_once(self):
        def fake_sdk(*args, **kwargs):
            kwargs["stdout"].write(self.capture)
        with patch.dict(os.environ, {"LOANHUB_SIGNATURE_BRIDGE_MODE": "staging"}), \
             patch.object(bridge.subprocess, "run", side_effect=fake_sdk), \
             contextlib.redirect_stdout(io.StringIO()):
            bridge.capture_wacom(self.actor)

    def test_offline_storage_then_idempotent_remote_ack(self):
        self._capture_once()
        with bridge.connection() as db:
            source, encrypted = db.execute(
                "SELECT signature_id, encrypted_signature FROM signatures"
            ).fetchone()
            self.assertNotEqual(encrypted, self.capture)
            restored = Fernet(bridge.key()).decrypt(encrypted)
            self.assertEqual(json.loads(restored)["format"], "loanhub-pen-strokes-v1")
            self.assertEqual(db.execute(
                "SELECT status FROM sync_outbox"
            ).fetchone()[0], "queued")
        outbound = []
        class Reply:
            status = 202
            def __init__(self, body):
                self.body = body
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return False
            def read(self):
                return json.dumps({
                    "status": "pending_identity_review",
                    "source_record_id": self.body["source_record_id"],
                }).encode()
        def fake_https(req, timeout):
            data = json.loads(req.data)
            self.assertEqual(req.get_header("X-company-id"), self.actor.company_id)
            self.assertEqual(data["source_record_id"], source)
            self.assertEqual(data["verified_signer_id"], self.actor.verified_signer_id)
            self.assertEqual(data["phone_numbers"], "26658123456/26663123456")
            self.assertEqual(data["capture_sha256"], hashlib.sha256(
                __import__("base64").b64decode(data["capture_base64"])
            ).hexdigest())
            outbound.append(data)
            return Reply(data)
        with patch.object(bridge.urllib.request, "urlopen", side_effect=fake_https), \
             contextlib.redirect_stdout(io.StringIO()):
            bridge.sync(argparse.Namespace(url=self.url), access_token="test-token")
            bridge.sync(argparse.Namespace(url=self.url), access_token="test-token")
        self.assertEqual(len(outbound), 1, "Acknowledged capture must not be uploaded again")
        with bridge.connection() as db:
            self.assertEqual(db.execute("SELECT status FROM sync_outbox").fetchone()[0], "acknowledged")
            self.assertEqual(db.execute("SELECT status FROM signatures").fetchone()[0], "pending_identity_review")

    def test_no_signer_consent_no_vault_record(self):
        self.actor.consent_confirmed = False
        with patch.dict(os.environ, {"LOANHUB_SIGNATURE_BRIDGE_MODE": "staging"}):
            with self.assertRaises(ValueError):
                bridge.capture_wacom(self.actor)
        self.assertFalse((bridge.HOME / "bridge.sqlite3").exists())


if __name__ == "__main__":
    unittest.main()
