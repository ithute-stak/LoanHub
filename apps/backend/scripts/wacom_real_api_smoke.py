#!/usr/bin/env python3
"""Controlled smoke test of the REAL LoanHub HTTPS API, never a Wacom VPS bridge.

Default mode: non-authenticated probes only, no customer data, no signatures.
Authenticated mode: use an explicitly provisioned synthetic test account.
Upload mode: opt-in, creates a synthetic PNG and stores it as pending review.
No approval, borrower signing or contract actions are performed.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import secrets
import struct
import sys
import urllib.error
import urllib.parse
import urllib.request
import zlib


class NoRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *_args, **_kwargs):
        return None


def must_be_test_origin(url: str) -> str:
    parsed = urllib.parse.urlsplit(url)
    if (
        parsed.scheme != "https" or not parsed.hostname or
        parsed.username is not None or parsed.password is not None or
        parsed.query or parsed.fragment or parsed.path not in ("", "/")
    ):
        raise ValueError("API origin must be an HTTPS host without credentials, paths or query")
    allowed = os.environ.get("WACOM_TEST_ALLOWED_HOST", "").strip().lower()
    if not allowed or parsed.hostname.lower() != allowed:
        raise ValueError("WACOM_TEST_ALLOWED_HOST must exactly match the test API hostname")
    if parsed.hostname.lower() in {"loanhub.co.ls", "ithute.co.ls", "api.loanhub.co.ls"}:
        raise ValueError("Public production API hostname is not permitted by smoke tester")
    return url.rstrip("/")


def synthetic_png() -> bytes:
    # Real decodable 16x8 RGBA PNG, no handwriting or pen data.
    width, height = 16, 8
    rows = b"".join(
        b"\x00" + b"".join(
            bytes((255, 255, 255, 255)) for _ in range(width)
        ) for _ in range(height)
    )
    def chunk(kind: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data)) + kind + data
            + struct.pack(">I", zlib.crc32(kind + data) & 0xffffffff)
        )
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(rows, level=6))
        + chunk(b"IEND", b"")
    )


class LoanHubAPI:
    def __init__(self, origin: str):
        self.origin = must_be_test_origin(origin)
        self._opener = urllib.request.build_opener(NoRedirects())
        self._token = ""
        self._company = ""

    def request(self, method: str, path: str, payload=None, authorized=False):
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        headers = {"Accept": "application/json", "User-Agent": "Wacom-API-Smoke/1"}
        if data is not None:
            headers["Content-Type"] = "application/json"
        if authorized:
            if not self._token or not self._company:
                raise RuntimeError("Login and selected company required")
            headers["Authorization"] = "Bearer " + self._token
            headers["X-Company-ID"] = self._company
        req = urllib.request.Request(
            self.origin + path, data=data, headers=headers, method=method
        )
        try:
            with self._opener.open(req, timeout=12) as response:
                content = response.read(65_537)
                if len(content) > 65_536:
                    raise RuntimeError("API response too large")
                return response.status, json.loads(content)
        except urllib.error.HTTPError as error:
            # Do not echo any server body (it may contain identifiers).
            return error.code, None
        except urllib.error.URLError as error:
            raise RuntimeError("Could not reach test API via trusted HTTPS") from error

    def login(self, company_id: str, phone: str, password: str, otp: str):
        status, response = self.request("POST", "/api/v1/auth/login", {
            "phone": phone, "password": password,
            "otp": otp or None, "device_name": "Wacom Synthetic API Smoke",
        })
        if status != 200 or not isinstance(response, dict):
            raise RuntimeError(f"Synthetic operator login failed (HTTP {status})")
        token = response.get("access_token")
        user = response.get("user") or {}
        memberships = user.get("memberships") or []
        if (
            not isinstance(token, str) or not token or
            user.get("must_change_password") is not False or
            user.get("is_active") is not True or
            not isinstance(memberships, list) or
            not any(
                isinstance(item, dict)
                and item.get("company_id") == company_id
                and item.get("is_active") is True
                for item in memberships
            )
        ):
            raise RuntimeError("Authenticated user does not belong to test company")
        self._token = token
        self._company = company_id

    def logout(self):
        self._token = ""
        self._company = ""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--origin", required=True, help="HTTPS origin of isolated LoanHub test API")
    parser.add_argument("--authenticated", action="store_true", help="Use synthetic operator credentials")
    parser.add_argument("--lookup", action="store_true", help="Lookup a synthetic National ID, requires --authenticated")
    parser.add_argument("--upload-operator-test", action="store_true", help="Store a disposable synthetic PNG, requires --authenticated and WACOM_TEST_UPLOAD=YES")
    args = parser.parse_args()

    if (args.lookup or args.upload_operator_test) and not args.authenticated:
        parser.error("--lookup and --upload-operator-test require --authenticated")
    if args.upload_operator_test and os.environ.get("WACOM_TEST_UPLOAD") != "YES":
        parser.error("Synthetic upload requires WACOM_TEST_UPLOAD=YES")
    if os.environ.get("WACOM_TEST_ENVIRONMENT") != "ISOLATED":
        parser.error("Set WACOM_TEST_ENVIRONMENT=ISOLATED to confirm target isolation")

    api = LoanHubAPI(args.origin)
    for path in (
        "/api/v1/local-signatures/me/status",
        "/api/v1/local-signatures/review",
    ):
        status, _ = api.request("GET", path)
        if status not in (401, 403):
            raise RuntimeError(f"Unauthenticated endpoint did not refuse access (HTTP {status})")
        print("PASS: protected API rejects unauthenticated access")

    if not args.authenticated:
        print("PASS: non-authenticated smoke test finished; no data read or written")
        return 0

    company = os.environ.get("WACOM_TEST_COMPANY_ID", "")
    phone = os.environ.get("WACOM_TEST_PHONE", "")
    password = os.environ.get("WACOM_TEST_PASSWORD", "")
    otp = os.environ.get("WACOM_TEST_OTP", "")
    if not company or not phone or not password:
        raise RuntimeError("Synthetic company ID, phone and password must be provided")
    try:
        api.login(company, phone, password, otp)
        print("PASS: authenticated synthetic staff member has active company membership")
        status, result = api.request(
            "GET", "/api/v1/local-signatures/me/status", authorized=True,
        )
        if status != 200 or not isinstance(result, dict) or result.get("company_id") != company:
            raise RuntimeError(f"Signature status not tenant-scoped (HTTP {status})")
        if result.get("usable_for_signing") is not False:
            raise RuntimeError("Unsafe operator signing status returned")
        print("PASS: operator status belongs to selected company; no signing enabled")

        if args.lookup:
            test_id = os.environ.get("WACOM_TEST_NATIONAL_ID", "")
            if not test_id.startswith("TEST-") or len(test_id) < 8:
                raise RuntimeError("Synthetic National ID must begin TEST-")
            status, found = api.request(
                "POST", "/api/v1/local-signatures/clients/lookup",
                {"national_id": test_id}, authorized=True,
            )
            if status != 200 or not isinstance(found, dict):
                raise RuntimeError(f"Client lookup failed (HTTP {status})")
            if found.get("may_sign_contract") is not False or found.get("may_reuse") is not False:
                raise RuntimeError("Unsafe client signing permissions returned")
            if found.get("status") not in {"matched", "not_found", "conflict"}:
                raise RuntimeError("Unexpected client lookup result status")
            if found["status"] == "matched" and (
                not isinstance(found.get("client"), dict)
                or not found["client"].get("borrower_id")
                or found["client"].get("signature_status") not in {
                    "missing", "pending_review", "verified_capture", "active",
                }
            ):
                raise RuntimeError("Matched client lookup has inconsistent shape")
            if found["status"] != "matched" and found.get("client") is not None:
                raise RuntimeError("Unmatched client unexpectedly returned identity")
            print("PASS: tenant client lookup handled; no customer details printed")

        if args.upload_operator_test:
            # Synthetic marker, *not* a real operator handwriting sample.
            # Never send real operator signatures through this smoke test.
            if result.get("signature_status") != "missing":
                raise RuntimeError("Synthetic operator does not require capture; upload skipped")
            raw = synthetic_png()
            marker = "TEST-WACOM-" + secrets.token_hex(6).upper()
            status, receipt = api.request(
                "POST", "/api/v1/local-signatures/captures",
                {
                    "signer_kind": "operator",
                    "consent_reference": marker,
                    "capture_png_base64": base64.b64encode(raw).decode("ascii"),
                    "capture_sha256": hashlib.sha256(raw).hexdigest(),
                },
                authorized=True,
            )
            if (
                status != 202 or not isinstance(receipt, dict)
                or receipt.get("status") != "pending_review"
                or receipt.get("usable_for_signing") is not False
                or not receipt.get("file_id")
            ):
                raise RuntimeError(f"Synthetic test upload not safely acknowledged (HTTP {status})")
            print("PASS: synthetic PNG stored by test API as pending review (never signed)")
            print("IMPORTANT: test evidence requires later cleanup in isolated environment")
    finally:
        api.logout()
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (RuntimeError, ValueError) as error:
        print(f"FAIL: {error}", file=sys.stderr)
        sys.exit(1)
