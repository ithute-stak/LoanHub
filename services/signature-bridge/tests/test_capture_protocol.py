import argparse
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

import bridge
from capture_protocol import MAX_BYTES, validate_strokes


def valid_capture():
    return json.dumps({
        "format": "loanhub-pen-strokes-v1",
        "strokes": [[
            {"x": 0.1, "y": 0.2, "pressure": 0.5, "t": 1},
            {"x": 0.2, "y": 0.3, "pressure": 0.6, "t": 3},
        ]],
    }).encode()


class CaptureTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.old_home = bridge.HOME
        bridge.HOME = Path(self.temp.name)

    def tearDown(self):
        bridge.HOME = self.old_home
        self.temp.cleanup()

    def test_valid_envelope(self):
        envelope = validate_strokes(valid_capture())
        self.assertEqual(envelope.stroke_count, 1)
        self.assertEqual(envelope.point_count, 2)

    def test_empty_and_out_of_bounds_rejected(self):
        for source in (
            b"{}",
            b'{"format":"loanhub-pen-strokes-v1","strokes":[]}',
            b'{"format":"loanhub-pen-strokes-v1","strokes":[[{"x":1.5,"y":0,"pressure":1,"t":1},{"x":0,"y":0,"pressure":1,"t":2}]]}',
            b'{"format":"loanhub-pen-strokes-v1","strokes":[[{"x":0,"y":0,"pressure":1,"t":2},{"x":0,"y":0,"pressure":1,"t":1}]]}',
            b"x" * (MAX_BYTES + 1),
        ):
            with self.subTest(source=source[:32]):
                with self.assertRaises(ValueError):
                    validate_strokes(source)

    def test_local_capture_requires_identity_and_consent(self):
        args = argparse.Namespace(
            company_id=str(uuid4()), signer_kind="client",
            verified_signer_id=str(uuid4()), phones="58123456",
            consent_reference="explicit-staging-consent",
            consent_confirmed=False, identity_verified=True,
        )
        with self.assertRaises(ValueError):
            bridge.capture_strokes(args)

    def test_verify_local_capture_returns_counts_without_signature_bytes(self):
        args = argparse.Namespace(
            company_id=str(uuid4()), signer_kind="client",
            verified_signer_id=str(uuid4()), phones="58123456",
            consent_reference="staging-test-only",
            consent_confirmed=True, identity_verified=True,
        )
        input_stream = io.TextIOWrapper(io.BytesIO(valid_capture()), encoding="utf-8")
        output = io.StringIO()
        with patch.object(bridge.sys, "stdin", input_stream), contextlib.redirect_stdout(output):
            bridge.capture_strokes(args)
        capture_id = json.loads(output.getvalue())["signature_id"]
        result = io.StringIO()
        with patch.dict(__import__("os").environ, {"LOANHUB_SIGNATURE_BRIDGE_MODE": "staging"}), contextlib.redirect_stdout(result):
            bridge.verify_local_capture(argparse.Namespace(signature_id=capture_id))
        report = json.loads(result.getvalue())
        self.assertTrue(report["capture_format_valid"])
        self.assertTrue(report["encrypted_at_rest"])
        self.assertEqual(report["stroke_count"], 1)
        self.assertEqual(report["point_count"], 2)
        self.assertEqual(report["queue_status"], "queued")
        self.assertFalse(report["contract_signed"])
        self.assertNotIn("pressure", result.getvalue())
        self.assertNotIn("strokes", result.getvalue())

    def test_verify_local_capture_refuses_production(self):
        with patch.dict(__import__("os").environ, {"LOANHUB_SIGNATURE_BRIDGE_MODE": "production"}):
            with self.assertRaises(ValueError):
                bridge.verify_local_capture(argparse.Namespace(signature_id=str(uuid4())))

    def test_local_capture_is_encrypted_and_queued(self):
        args = argparse.Namespace(
            company_id=str(uuid4()), signer_kind="client",
            verified_signer_id=str(uuid4()), phones="58123456/63123456",
            consent_reference="explicit-staging-consent",
            consent_confirmed=True, identity_verified=True,
        )
        stdin = io.TextIOWrapper(io.BytesIO(valid_capture()), encoding="utf-8")
        with patch.object(bridge.sys, "stdin", stdin), contextlib.redirect_stdout(io.StringIO()):
            bridge.capture_strokes(args)
        with bridge.connection() as db:
            row = db.execute("SELECT encrypted_signature FROM signatures").fetchone()
            self.assertIsNotNone(row)
            self.assertNotIn(b"loanhub-pen-strokes-v1", row[0])
            self.assertEqual(db.execute("SELECT COUNT(*) FROM sync_outbox").fetchone()[0], 1)


if __name__ == "__main__":
    unittest.main()
