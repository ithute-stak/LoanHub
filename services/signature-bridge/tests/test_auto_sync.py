"""Fail-closed unattended sync configuration and token-provider tests."""
import os
import stat
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import bridge


class AutoSyncTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.provider = Path(self.temp.name) / "token-provider"
        self.provider.write_text("#!/bin/sh\nprintf 'test-only-token'\n")
        self.provider.chmod(0o700)

    def tearDown(self):
        self.temp.cleanup()

    def configuration(self):
        return {
            "LOANHUB_SIGNATURE_BRIDGE_AUTO_SYNC_ENABLED": "true",
            "LOANHUB_SIGNATURE_BRIDGE_MODE": "staging",
            "LOANHUB_SIGNATURE_BRIDGE_SYNC_URL":
                "https://staging.example.com/api/v1/signature-bridge/imports",
            "LOANHUB_SIGNATURE_BRIDGE_TOKEN_PROVIDER": str(self.provider),
        }

    def test_disabled_without_opt_in(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertIsNone(bridge.auto_sync_config())

    def test_rejects_production_mode(self):
        with patch.dict(os.environ, {**self.configuration(),
                                     "LOANHUB_SIGNATURE_BRIDGE_MODE": "production"}, clear=True):
            with self.assertRaises(ValueError):
                bridge.auto_sync_config()

    def test_rejects_world_readable_token_provider(self):
        self.provider.chmod(0o755)
        with patch.dict(os.environ, self.configuration(), clear=True):
            with self.assertRaises(ValueError):
                bridge.auto_sync_config()

    def test_accepts_private_staging_provider(self):
        with patch.dict(os.environ, self.configuration(), clear=True):
            self.assertEqual(bridge.auto_sync_config()[1], str(self.provider))

    def test_token_only_passed_in_memory(self):
        calls = []
        def receive(args, *, access_token):
            calls.append(access_token)
        with patch.object(bridge, "sync", side_effect=receive):
            bridge.sync_using_provider(self.configuration()[
                "LOANHUB_SIGNATURE_BRIDGE_SYNC_URL"], str(self.provider))
        self.assertEqual(calls, ["test-only-token"])


if __name__ == "__main__":
    unittest.main()
