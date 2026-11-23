"""Offline tests for isolated Data Center certification preflight (no Docker or VPS writes)."""
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SOURCE = ROOT / "scripts" / "data-center-cert-preflight.py"

class PreflightTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = pathlib.Path(self.temp.name)
        (self.base / "scripts").mkdir()
        (self.base / "scripts" / "data-center-cert-preflight.py").write_bytes(SOURCE.read_bytes())
        (self.base / "compose.dc-cert.yml").write_text("name: loanhub-dc-cert\n")
        keys = self.base / "dc-cert-secrets"
        keys.mkdir()
        (keys / "jwt_private.pem").write_text("synthetic-only")
        (keys / "jwt_public.pem").write_text("synthetic-only")
        self.values = [
            "DC_CERT_DB_PASSWORD=synthetic-unrelated-secret",
            "DC_CERT_APP_ORIGIN=https://staging.example.test",
            "DC_CERT_API_URL=https://api.staging.example.test/api/v1",
        ]

    def run_preflight(self):
        (self.base / ".env.dc-staging").write_text("\n".join(self.values) + "\n")
        environment = os.environ.copy()
        for key in ("DC_CERT_APP_ORIGIN", "DC_CERT_API_URL", "DC_CERT_DB_PASSWORD"):
            environment.pop(key, None)
        return subprocess.run(
            [sys.executable, str(self.base / "scripts" / "data-center-cert-preflight.py")],
            text=True, capture_output=True, env=environment, check=False,
        )

    def test_synthetic_staging_configuration_accepted(self):
        result = self.run_preflight()
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_public_production_endpoint_refused(self):
        self.values[1] = "DC_CERT_APP_ORIGIN=https://loanhub.co.ls"
        result = self.run_preflight()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("production endpoint", result.stderr)

    def test_payment_credentials_refused(self):
        self.values.append("MPESA_API_KEY=real-looking-key")
        result = self.run_preflight()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("MPESA_API_KEY", result.stderr)
        self.assertNotIn("real-looking-key", result.stderr)

    def test_external_database_url_refused(self):
        self.values.append("DATABASE_URL=postgresql://example.net/production")
        result = self.run_preflight()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("DATABASE_URL", result.stderr)

    def test_production_database_override_refused(self):
        self.values.append("DB_HOST=prod-db")
        result = self.run_preflight()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("DB_HOST", result.stderr)

    def test_missing_separate_private_key_refused(self):
        (self.base / "dc-cert-secrets" / "jwt_private.pem").unlink()
        result = self.run_preflight()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("signing material", result.stderr)

if __name__ == "__main__":
    unittest.main()
