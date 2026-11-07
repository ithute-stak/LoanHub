"""Read-only Wacom staging deployment gate: safe by default."""
import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "wacom_staging_readiness.py"
spec = importlib.util.spec_from_file_location("wacom_staging_readiness", SCRIPT)
assert spec and spec.loader
stage = importlib.util.module_from_spec(spec)
spec.loader.exec_module(stage)


def staging_env():
    return {
        "WACOM_TEST_ENVIRONMENT": "ISOLATED",
        "WACOM_TEST_ALLOWED_HOST": "test-api.example.invalid",
        "WACOM_TEST_API_ORIGIN": "https://test-api.example.invalid",
        "ENVIRONMENT": "staging",
        "DATABASE_URL": "postgresql+psycopg2://synthetic:synthetic@127.0.0.1:5432/wacom_test",
        "FILE_ENCRYPTION_ENABLED": "true",
        "FILE_ENCRYPTION_KEY": "synthetic-fixture-only",
        "MALWARE_SCAN_ENABLED": "true",
        "MALWARE_SCAN_FAIL_CLOSED": "true",
        "CLAMAV_HOST": "clamav-test",
        "FILE_STORAGE_BACKEND": "local",
        "FILE_STORAGE_PATH": "/var/lib/loanhub/staging",
    }


def test_isolated_configuration_passes():
    assert stage.readiness(staging_env()) == []


def test_production_host_not_allowed():
    env = staging_env()
    env["WACOM_TEST_ALLOWED_HOST"] = "api.loanhub.co.ls"
    env["WACOM_TEST_API_ORIGIN"] = "https://api.loanhub.co.ls"
    assert "unsafe_api_origin" in stage.readiness(env)


def test_no_encryption_and_no_scanner_fail_closed():
    env = staging_env()
    env["FILE_ENCRYPTION_ENABLED"] = "false"
    env["MALWARE_SCAN_ENABLED"] = "false"
    env["MALWARE_SCAN_FAIL_CLOSED"] = "false"
    failures = stage.readiness(env)
    assert "file_encryption_disabled" in failures
    assert "malware_scan_disabled" in failures
    assert "malware_scan_not_fail_closed" in failures


def test_nonisolated_database_or_file_storage_blocks():
    env = staging_env()
    env["DATABASE_URL"] = "postgresql://synthetic:synthetic@127.0.0.1:5432/loan_db"
    env["FILE_STORAGE_PATH"] = "/var/lib/loanhub/production"
    failures = stage.readiness(env)
    assert "database_not_named_for_isolation" in failures
    assert "local_storage_path_not_explicitly_staged" in failures


def test_s3_requires_dedicated_test_bucket():
    env = staging_env()
    env["FILE_STORAGE_BACKEND"] = "s3"
    env["S3_BUCKET"] = "loan-documents"
    assert "bucket_not_explicitly_staged" in stage.readiness(env)
    env["S3_BUCKET"] = "loanhub-staging-documents"
    assert stage.readiness(env) == []


def test_missing_secrets_report_codes_not_secret_values():
    env = staging_env()
    env["DATABASE_URL"] = "not-a-valid-url"
    env["FILE_ENCRYPTION_KEY"] = ""
    issues = stage.readiness(env)
    assert "invalid_database_url" in issues
    assert "dedicated_file_encryption_key_missing" in issues
    assert "synthetic" not in " ".join(issues)
