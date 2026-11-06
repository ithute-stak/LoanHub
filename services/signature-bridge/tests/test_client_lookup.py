"""No-network tests for the staging National ID lookup adapter."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from uuid import uuid4

import client_lookup


class LookupTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.provider = Path(self.tmp.name) / "token-helper"
        self.provider.write_text("#!/bin/sh\nprintf temporary-test-token\n")
        self.provider.chmod(0o700)
        self.company = str(uuid4())
        self.url = "https://staging.example.invalid/api/v1/signature-bridge/lookup-national-id"
        self.mode = patch.dict(os.environ, {"LOANHUB_SIGNATURE_BRIDGE_MODE": "staging"})
        self.mode.start()

    def tearDown(self):
        self.mode.stop()
        self.tmp.cleanup()

    def test_private_lookup_profile_uses_no_token_in_file(self):
        config = Path(self.tmp.name) / "lookup.json"
        config.write_text(json.dumps({
            "url": self.url, "company_id": self.company,
            "token_provider": str(self.provider)
        }))
        config.chmod(0o600)
        found = client_lookup.load_lookup_config(config)
        self.assertEqual(found["company_id"], self.company)
        self.assertEqual(found["token_provider"], self.provider)
        config.chmod(0o644)
        with self.assertRaises(ValueError):
            client_lookup.load_lookup_config(config)

    def test_lookup_profile_rejects_embedded_token(self):
        config = Path(self.tmp.name) / "lookup.json"
        config.write_text(json.dumps({
            "url": self.url, "company_id": self.company,
            "token_provider": str(self.provider), "token": "must-not-store"
        }))
        config.chmod(0o600)
        with self.assertRaises(ValueError):
            client_lookup.load_lookup_config(config)

    def test_rejects_production_hostname_and_http(self):
        for url in (
            "https://loanhub.co.ls/api/v1/signature-bridge/lookup-national-id",
            "http://staging.example.invalid/api/v1/signature-bridge/lookup-national-id",
            "https://staging.example.invalid/api/v1/signature-bridge/lookup-national-id?redirect=yes",
        ):
            with self.assertRaises(ValueError):
                client_lookup.validate_lookup_endpoint(url)

    def test_exact_tenant_bound_lookup_no_raw_id_printed(self):
        borrower = str(uuid4())
        body = {"status": "existing_signature", "matches": [
            {"borrower_id": borrower, "full_name": "Test Borrower",
             "national_id_suffix": "1234", "signature_state": "active_saved"}
        ], "may_capture": False, "may_reuse": False, "may_sign_contract": False}
        class Reply:
            status = 200
            def __enter__(self): return self
            def __exit__(self, *_): return False
            def read(self, maximum):
                return json.dumps(body).encode()
        def fake_open(req, timeout):
            self.assertEqual(req.get_header("X-company-id"), self.company)
            self.assertEqual(json.loads(req.data)["national_id"], "DEMO1234")
            self.assertEqual(req.get_header("Authorization"), "Bearer temporary-test-token")
            return Reply()
        fake_opener = type("Opener", (), {"open": staticmethod(fake_open)})()
        token_result = type("Token", (), {"stdout": "temporary-test-token"})()
        with patch.object(client_lookup.subprocess, "run", return_value=token_result), \
             patch.object(client_lookup.urllib.request, "build_opener", return_value=fake_opener):
            result = client_lookup.lookup_client(url=self.url, company_id=self.company,
                token_provider=self.provider, national_id="DEMO1234")
        self.assertEqual(result["status"], "existing_signature")
        self.assertFalse(result["may_capture"])

    def test_blocks_signing_rights_from_untrusted_response(self):
        body = {"status": "not_found", "matches": [],
                "may_capture": True, "may_reuse": False, "may_sign_contract": False}
        class Reply:
            status = 200
            def __enter__(self): return self
            def __exit__(self, *_): return False
            def read(self, maximum): return json.dumps(body).encode()
        opener = type("Opener", (), {"open": staticmethod(lambda req, timeout: Reply())})()
        token = type("Token", (), {"stdout": "short-lived"})()
        with patch.object(client_lookup.subprocess, "run", return_value=token), \
             patch.object(client_lookup.urllib.request, "build_opener", return_value=opener):
            with self.assertRaisesRegex(ValueError, "signing rights"):
                client_lookup.lookup_client(url=self.url, company_id=self.company,
                    token_provider=self.provider, national_id="DEMO1234")

    def test_rejects_insecure_token_helper_without_execution(self):
        self.provider.chmod(0o777)
        with patch.object(client_lookup.subprocess, "run") as run:
            with self.assertRaisesRegex(ValueError, "0700"):
                client_lookup.lookup_client(url=self.url, company_id=self.company,
                    token_provider=self.provider, national_id="DEMO1234")
        run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
