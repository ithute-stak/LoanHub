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
        self.mode = patch.dict(os.environ, {"LOANHUB_SIGNATURE_BRIDGE_MODE": "staging"})
        self.mode.start()

    def tearDown(self):
        self.mode.stop()
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

    def test_explicit_sync_refuses_non_staging_without_network(self):
        self.prepare()
        with patch.dict(os.environ, {"LOANHUB_SIGNATURE_BRIDGE_MODE": "production"}), \
             patch.object(bridge.urllib.request, "build_opener") as network:
            with self.assertRaisesRegex(ValueError, "requires staging mode"):
                bridge.sync(
                    argparse.Namespace(url="https://staging.example.com/api/v1/signature-bridge/imports"),
                    access_token="test-token",
                )
        network.assert_not_called()
        with bridge.connection() as db:
            self.assertEqual(
                db.execute("SELECT status FROM sync_outbox").fetchone()[0],
                "queued",
            )

    def test_read_only_preflight_never_makes_network_request(self):
        self.prepare()
        out = io.StringIO()
        with patch.object(bridge.urllib.request, "build_opener") as network:
            with contextlib.redirect_stdout(out):
                bridge.staging_import_preflight(argparse.Namespace())
        network.assert_not_called()
        result = json.loads(out.getvalue())
        self.assertEqual(result["queued_records"], 1)
        self.assertEqual(result["network_requests"], 0)
        self.assertFalse(result["ready_to_sync"])
        self.assertFalse(result["identity_evidence_verified"])
        self.assertFalse(result["consent_evidence_verified"])
        self.assertNotIn("26658123456", out.getvalue())

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
                    "company_id": company,
                    "usable_for_signing": False,
                }).encode()

        def fake_open(req, timeout):
            self.assertEqual(req.get_header("X-company-id"), company)
            self.assertTrue(req.full_url.startswith("https://"))
            payload = json.loads(req.data)
            requests.append(payload)
            return Reply(payload)

        args = argparse.Namespace(url="https://staging.example.com/api/v1/signature-bridge/imports")
        with patch.dict(os.environ, {"LOANHUB_SIGNATURE_BRIDGE_ACCESS_TOKEN": "staging-test-token"}), \
             patch.object(bridge.urllib.request, "build_opener", return_value=type("Opener", (), {"open": staticmethod(fake_open)})()):
            with contextlib.redirect_stdout(io.StringIO()):
                bridge.sync(args)
                bridge.sync(args)
        self.assertEqual(len(requests), 1)
        self.assertEqual(requests[0]["phone_numbers"], "26658123456/26663123456")
        with bridge.connection() as db:
            self.assertEqual(db.execute("SELECT status FROM sync_outbox").fetchone()[0], "acknowledged")

    def test_wrong_tenant_acknowledgement_does_not_clear_queue(self):
        company = self.prepare()
        class Reply:
            status = 202
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return False
            def read(self):
                return json.dumps({
                    "status": "pending_identity_review",
                    "source_record_id": payload["source_record_id"],
                    "company_id": str(uuid4()),
                    "usable_for_signing": False,
                }).encode()
        payload = {}
        def wrong_tenant(req, timeout):
            payload.update(json.loads(req.data))
            return Reply()
        args = argparse.Namespace(url="https://staging.example.com/api/v1/signature-bridge/imports")
        with patch.object(bridge.urllib.request, "build_opener", return_value=type(
            "Opener", (), {"open": staticmethod(wrong_tenant)})()), \
             contextlib.redirect_stderr(io.StringIO()):
            bridge.sync(args, access_token="test-token")
        with bridge.connection() as db:
            self.assertEqual(db.execute("SELECT status FROM sync_outbox").fetchone()[0], "queued")
        self.assertNotEqual(company, payload.get("company_id"))


    def test_acknowledgement_claiming_signing_rights_is_rejected(self):
        company = self.prepare()
        payload = {}
        class Reply:
            status = 202
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return False
            def read(self):
                return json.dumps({
                    "status": "pending_identity_review",
                    "source_record_id": payload["source_record_id"],
                    "company_id": company,
                    "usable_for_signing": True,
                }).encode()
        def unauthorized(req, timeout):
            payload.update(json.loads(req.data))
            return Reply()
        with patch.object(bridge.urllib.request, "build_opener", return_value=type(
            "Opener", (), {"open": staticmethod(unauthorized)})()), \
             contextlib.redirect_stderr(io.StringIO()):
            bridge.sync(argparse.Namespace(url="https://staging.example.com/api/v1/signature-bridge/imports"), access_token="test-token")
        with bridge.connection() as db:
            self.assertEqual(db.execute("SELECT status FROM sync_outbox").fetchone()[0], "queued")


    def test_failed_connection_retains_queue(self):
        self.prepare()
        args = argparse.Namespace(url="https://staging.example.com/api/v1/signature-bridge/imports")
        with patch.dict(os.environ, {"LOANHUB_SIGNATURE_BRIDGE_ACCESS_TOKEN": "test-token"}), \
             patch.object(bridge.urllib.request, "build_opener", return_value=type("Opener", (), {"open": staticmethod(lambda req, timeout: (_ for _ in ()).throw(OSError("disconnected")))})()):
            with contextlib.redirect_stderr(io.StringIO()):
                bridge.sync(args)
        with bridge.connection() as db:
            self.assertEqual(db.execute("SELECT status, retry_count FROM sync_outbox").fetchone(),
                             ("queued", 1))

    def test_rejects_http_url(self):
        with patch.dict(os.environ, {"LOANHUB_SIGNATURE_BRIDGE_ACCESS_TOKEN": "token"}):
            with self.assertRaises(ValueError):
                bridge.sync(argparse.Namespace(url="http://localhost/api/v1/signature-bridge/imports"))

    def test_rejects_untrusted_redirect_and_query_string(self):
        with self.assertRaises(ValueError):
            bridge.NoRedirect().redirect_request(None, None, 307, "Temporary Redirect", {}, "https://other.example.invalid")
        for target in (
            "https://staging.example.com/api/v1/signature-bridge/imports?next=https://evil.example",
            "https://staging.example.com/api/v1/signature-bridge/imports#fragment",
            "https://user:password@staging.example.com/api/v1/signature-bridge/imports",
        ):
            with self.subTest(target=target):
                with self.assertRaises(ValueError):
                    bridge.validate_sync_url(target)


if __name__ == "__main__":
    unittest.main()
