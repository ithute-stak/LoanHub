"""Preflight must not call the network or execute the credential helper."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from uuid import uuid4

import lookup_preflight


class PreflightTests(unittest.TestCase):
    def test_missing_config_fails_closed(self):
        with tempfile.TemporaryDirectory() as folder:
            passed, message = lookup_preflight.assess(Path(folder) / "no-such-profile.json")
            self.assertFalse(passed)
            self.assertIn("missing", message)

    def test_private_staging_profile_validated_without_network_or_helper(self):
        with tempfile.TemporaryDirectory() as folder:
            config = Path(folder) / "lookup.json"
            helper = Path(folder) / "token-helper"
            helper.write_text("#!/bin/sh\nexit 99\n")
            helper.chmod(0o700)
            config.write_text(json.dumps({
                "url": "https://staging.example.invalid/api/v1/signature-bridge/lookup-national-id",
                "company_id": str(uuid4()),
                "token_provider": str(helper),
            }))
            config.chmod(0o600)
            with patch("subprocess.run") as execute, patch("urllib.request.build_opener") as network:
                passed, message = lookup_preflight.assess(config)
            self.assertTrue(passed)
            self.assertIn("NOT verified", message)
            execute.assert_not_called()
            network.assert_not_called()

    def test_production_api_host_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            config = Path(folder) / "lookup.json"
            helper = Path(folder) / "token-helper"
            helper.write_text("#!/bin/sh\nexit 0\n")
            helper.chmod(0o700)
            config.write_text(json.dumps({
                "url": "https://api.loanhub.co.ls/api/v1/signature-bridge/lookup-national-id",
                "company_id": str(uuid4()),
                "token_provider": str(helper),
            }))
            config.chmod(0o600)
            passed, message = lookup_preflight.assess(config)
            self.assertFalse(passed)
            self.assertNotIn("api.loanhub.co.ls", message)


if __name__ == "__main__":
    unittest.main()
