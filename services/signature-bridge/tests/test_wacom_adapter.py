"""Mockable SDK adapter boundary; does not use any physical device."""
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


class WacomAdapterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.original = bridge.HOME
        bridge.HOME = Path(self.temp.name) / "vault"
        self.adapter = Path(self.temp.name) / "wacom-test-adapter"
        self.adapter.write_text("#!/bin/sh\n")
        self.adapter.chmod(0o700)
        self.args = argparse.Namespace(
            sdk_adapter=str(self.adapter), consent_confirmed=True,
            identity_verified=True, company_id=str(uuid4()),
            signer_kind="client", verified_signer_id=str(uuid4()),
            phones="58123456 / 63123456",
            consent_reference="staging-example-consent",
        )
        self.env = patch.dict(os.environ, {"LOANHUB_SIGNATURE_BRIDGE_MODE": "staging"})
        self.env.start()
        self.sample = json.dumps({
            "format": "loanhub-pen-strokes-v1",
            "strokes": [[
                {"x": .1, "y": .2, "pressure": .5, "t": 1},
                {"x": .2, "y": .3, "pressure": .7, "t": 2},
            ]],
        }).encode()

    def tearDown(self):
        self.env.stop()
        bridge.HOME = self.original
        self.temp.cleanup()

    def test_adapter_receipt_vaulted_and_queued(self):
        def write_strokes(*argv, **kwargs):
            kwargs["stdout"].write(self.sample)
        with patch.object(bridge.subprocess, "run", side_effect=write_strokes) as run:
            with contextlib.redirect_stdout(io.StringIO()):
                bridge.capture_wacom(self.args)
        run.assert_called_once()
        self.assertEqual(run.call_args.args[0], [str(self.adapter), "--capture-strokes-json"])
        with bridge.connection() as db:
            row = db.execute("SELECT encrypted_signature FROM signatures").fetchone()
            self.assertIsNotNone(row)
            self.assertNotIn(b"loanhub-pen-strokes-v1", row[0])
            self.assertEqual(db.execute("SELECT COUNT(*) FROM sync_outbox").fetchone()[0], 1)

    def test_blocks_without_consent(self):
        self.args.consent_confirmed = False
        with patch.object(bridge.subprocess, "run") as run:
            with self.assertRaises(ValueError):
                bridge.capture_wacom(self.args)
        run.assert_not_called()

    def test_blocks_world_writable_executable(self):
        self.adapter.chmod(0o777)
        with patch.object(bridge.subprocess, "run") as run:
            with self.assertRaises(ValueError):
                bridge.capture_wacom(self.args)
        run.assert_not_called()

    def test_rejects_invalid_hardware_output_without_storage(self):
        def write_invalid(*argv, **kwargs):
            kwargs["stdout"].write(b"not-json")
        with patch.object(bridge.subprocess, "run", side_effect=write_invalid):
            with self.assertRaises(ValueError):
                bridge.capture_wacom(self.args)
        self.assertFalse((bridge.HOME / "bridge.sqlite3").exists())

    def test_expired_adapter_never_creates_record(self):
        with patch.object(bridge.subprocess, "run",
                          side_effect=bridge.subprocess.TimeoutExpired("test", 35)):
            with self.assertRaises(ValueError):
                bridge.capture_wacom(self.args)
        self.assertFalse((bridge.HOME / "bridge.sqlite3").exists())

    def test_refuses_capture_outside_staging(self):
        with patch.dict(os.environ, {"LOANHUB_SIGNATURE_BRIDGE_MODE": "production"}):
            with patch.object(bridge.subprocess, "run") as run:
                with self.assertRaises(ValueError):
                    bridge.capture_wacom(self.args)
        run.assert_not_called()

    def test_concurrent_capture_lock_fails_closed(self):
        with bridge.exclusive_capture_lock():
            with self.assertRaises(ValueError):
                with bridge.exclusive_capture_lock():
                    pass

    def test_unbounded_output_rejected(self):
        def flood(*argv, **kwargs):
            kwargs["stdout"].write(b"x" * 140000)
        with patch.object(bridge.subprocess, "run", side_effect=flood):
            with self.assertRaises(ValueError):
                bridge.capture_wacom(self.args)
        self.assertFalse((bridge.HOME / "bridge.sqlite3").exists())


if __name__ == "__main__":
    unittest.main()
