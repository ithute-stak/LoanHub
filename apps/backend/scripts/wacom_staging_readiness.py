#!/usr/bin/env python3
"""Wacom isolation gate for existing LoanHub staging backend (read-only).

Checks explicit environmental safety invariants. Does not load secrets into
logs, open DB/network connections, migrate, create files or deploy anything.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
from urllib.parse import urlsplit

from sqlalchemy.engine import make_url


def readiness(environment: dict[str, str]) -> list[str]:
    failures: list[str] = []

    def required(name: str) -> str:
        value = environment.get(name, "").strip()
        if not value:
            failures.append(name + "_missing")
        return value

    if required("WACOM_TEST_ENVIRONMENT") != "ISOLATED":
        failures.append("not_confirmed_isolated_environment")

    hostname = required("WACOM_TEST_ALLOWED_HOST").lower()
    origin = required("WACOM_TEST_API_ORIGIN")
    parsed = urlsplit(origin)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path not in ("", "/")
        or parsed.query or parsed.fragment
        or parsed.hostname.lower() != hostname
        or hostname in {"loanhub.co.ls", "api.loanhub.co.ls", "ithute.co.ls"}
    ):
        failures.append("unsafe_api_origin")

    if environment.get("ENVIRONMENT", "").lower() not in {"test", "staging"}:
        failures.append("non_staging_backend_environment")

    url = required("DATABASE_URL")
    try:
        parsed_db = make_url(url)
        if (
            parsed_db.get_backend_name() != "postgresql"
            or not parsed_db.database
            or not parsed_db.database.endswith(("_test", "_staging"))
            or not parsed_db.host
        ):
            failures.append("database_not_named_for_isolation")
    except Exception:
        failures.append("invalid_database_url")

    if environment.get("FILE_ENCRYPTION_ENABLED", "").lower() not in {"true", "1"}:
        failures.append("file_encryption_disabled")
    if not environment.get("FILE_ENCRYPTION_KEY", ""):
        failures.append("dedicated_file_encryption_key_missing")
    if environment.get("MALWARE_SCAN_ENABLED", "").lower() not in {"true", "1"}:
        failures.append("malware_scan_disabled")
    if environment.get("MALWARE_SCAN_FAIL_CLOSED", "").lower() not in {"true", "1"}:
        failures.append("malware_scan_not_fail_closed")
    if not environment.get("CLAMAV_HOST", "").strip():
        failures.append("clamav_host_missing")

    provider = environment.get("FILE_STORAGE_BACKEND", "").lower()
    if provider == "local":
        path = environment.get("FILE_STORAGE_PATH", "").strip()
        if not path or path in {"/", "/tmp", "./"}:
            failures.append("local_storage_path_not_isolated")
        else:
            try:
                p = Path(path).expanduser()
                if not p.is_absolute() or not any(
                    token in p.parts[-2:] for token in ("test", "staging", "wacom-test")
                ):
                    failures.append("local_storage_path_not_explicitly_staged")
            except (ValueError, OSError):
                failures.append("invalid_local_storage_path")
    elif provider in {"s3", "minio"}:
        bucket = environment.get("S3_BUCKET", "").lower()
        if not bucket or not any(token in bucket for token in ("test", "staging")):
            failures.append("bucket_not_explicitly_staged")
    else:
        failures.append("unknown_storage_backend")

    return sorted(set(failures))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", required=True)
    args = parser.parse_args()
    failures = readiness(dict(os.environ))
    if failures:
        print("WACOM STAGING READINESS: BLOCKED")
        for item in failures:
            print("BLOCKER:", item)
        return 1
    print("WACOM STAGING READINESS: ENVIRONMENT CONFIGURATION PASSED")
    print("This is a static gate only: no API, database, scanner or storage probed.")
    print("An isolated environment and synthetic end-to-end tests are still required.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
