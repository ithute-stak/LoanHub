"""Authenticated staging-only National ID lookup. No credentials or IDs logged.

This client requires an externally provisioned ephemeral token-provider executable.
It never accesses the production site and never stores bearer tokens or National IDs.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import stat
import subprocess
import urllib.request
import urllib.parse
from uuid import UUID


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("National ID lookup redirect prohibited")


def validate_lookup_endpoint(url: str) -> None:
    parts = urllib.parse.urlsplit(url)
    if (parts.scheme != "https" or not parts.hostname or
            parts.username is not None or parts.password is not None or
            parts.query or parts.fragment or parts.port not in (None, 443) or
            parts.path != "/api/v1/signature-bridge/lookup-national-id" or
            parts.hostname.lower() in ("localhost", "127.0.0.1", "loanhub.co.ls",
                                       "www.loanhub.co.ls", "api.loanhub.co.ls")):
        raise ValueError("Use an approved dedicated staging HTTPS National ID endpoint")


def load_lookup_config(path: Path) -> dict:
    """Load metadata only; never persist tokens or real National IDs."""
    if not path.is_absolute():
        raise ValueError("Lookup config must be an absolute path")
    info = path.lstat()
    if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
            or info.st_mode & 0o077):
        raise ValueError("Lookup config must be private and owned by the operator")
    if info.st_size > 4096:
        raise ValueError("Lookup config too large")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or set(data) != {"url", "company_id", "token_provider"}:
        raise ValueError("Lookup config must specify URL, company and token provider only")
    validate_lookup_endpoint(data["url"])
    data["company_id"] = str(UUID(data["company_id"]))
    provider = Path(data["token_provider"])
    if not provider.is_absolute():
        raise ValueError("Token provider path must be absolute")
    info = provider.lstat()
    if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
            or info.st_mode & 0o077 or not info.st_mode & stat.S_IXUSR):
        raise ValueError("Token provider must be private and executable")
    return {"url": data["url"], "company_id": data["company_id"],
            "token_provider": provider}


def lookup_client(*, url: str, company_id: str, token_provider: Path, national_id: str) -> dict:
    if os.getenv("LOANHUB_SIGNATURE_BRIDGE_MODE") != "staging":
        raise ValueError("Client lookup requires staging mode")
    validate_lookup_endpoint(url)
    company = str(UUID(company_id))
    national_id = national_id.strip()
    if not re.fullmatch(r"[A-Za-z0-9/-]{4,32}", national_id):
        raise ValueError("National ID has invalid characters or length")
    if not token_provider.is_absolute():
        raise ValueError("Token provider must be an absolute executable path")
    info = token_provider.lstat()
    if (not stat.S_ISREG(info.st_mode) or
            info.st_uid != os.getuid() or info.st_mode & 0o077 or
            not info.st_mode & stat.S_IXUSR):
        raise ValueError("Token provider must be owner-only 0700")
    result = subprocess.run(
        [str(token_provider)], capture_output=True, text=True, timeout=10,
        check=True, env={"HOME": str(Path.home()), "PATH": "/usr/bin:/bin"},
    )
    token = result.stdout.strip()
    if not token or len(token) > 4096 or any(c.isspace() for c in token):
        raise ValueError("Operator session unavailable")
    request = urllib.request.Request(
        url,
        method="POST",
        data=json.dumps({"national_id": national_id}).encode("utf-8"),
        headers={"Authorization": "Bearer " + token,
                 "X-Company-ID": company,
                 "Content-Type": "application/json"},
    )
    opener = urllib.request.build_opener(NoRedirect())
    with opener.open(request, timeout=8) as response:
        if response.status != 200:
            raise ValueError("Client lookup was not approved")
        raw = response.read(4097)
    if len(raw) > 4096:
        raise ValueError("Lookup response is too large")
    data = json.loads(raw)
    allowed = {"existing_signature", "pending_signature_review",
               "matched_no_signature", "not_found", "conflict"}
    if not isinstance(data, dict) or data.get("status") not in allowed:
        raise ValueError("Unexpected client lookup response")
    if (data.get("may_capture") is not False or
            data.get("may_reuse") is not False or
            data.get("may_sign_contract") is not False):
        raise ValueError("Lookup response attempted to grant signing rights")
    matches = data.get("matches")
    if not isinstance(matches, list) or len(matches) > 1:
        raise ValueError("Invalid client match count")
    if data["status"] in ("existing_signature", "pending_signature_review", "matched_no_signature"):
        if len(matches) != 1 or not isinstance(matches[0].get("full_name"), str):
            raise ValueError("Missing exact client match")
        UUID(matches[0]["borrower_id"])
    elif matches:
        raise ValueError("Unexpected client identity disclosure")
    return data
