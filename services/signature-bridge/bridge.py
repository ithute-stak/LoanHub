#!/usr/bin/env python3
"""Offline-first LoanHub Signature Bridge (staging foundation).

No document signing, capture-device control or remote uploads are enabled here.
Only verified signer links may be imported; phone lookup is advisory.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import signal
import sqlite3
import sys
import time
from pathlib import Path

from cryptography.fernet import Fernet

HOME = Path(os.environ.get("LOANHUB_SIGNATURE_BRIDGE_HOME", str(Path.home() / ".local/share/loanhub-signature-bridge")))
STOP = False

def normalize_phone(raw: str) -> str:
    value = re.sub(r"[\s()\-]", "", raw)
    if value.startswith("00266"):
        value = value[5:]
    elif value.startswith("+266"):
        value = value[4:]
    elif value.startswith("266") and len(value) == 11:
        value = value[3:]
    if not re.fullmatch(r"[0-9]{8}", value):
        raise ValueError("Expected an eight-digit Lesotho number")
    return "266" + value

def split_phones(value: str) -> list[str]:
    if not isinstance(value, str):
        raise ValueError("Phone field must be text")
    parts = value.split("/")
    if not 1 <= len(parts) <= 8 or any(not p.strip() for p in parts):
        raise ValueError("Expected 1-8 nonempty slash-separated phone numbers")
    return list(dict.fromkeys(normalize_phone(p.strip()) for p in parts))

def state_dir() -> Path:
    HOME.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(HOME, 0o700)
    return HOME

def key() -> bytes:
    folder = state_dir()
    location = folder / "vault.key"
    if not location.exists():
        value = Fernet.generate_key()
        fd = os.open(location, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as handle:
            handle.write(value)
    if location.stat().st_mode & 0o077:
        raise RuntimeError("Insecure vault key permissions")
    return location.read_bytes()

def connection() -> sqlite3.Connection:
    folder = state_dir()
    dbpath = folder / "bridge.sqlite3"
    db = sqlite3.connect(dbpath)
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA foreign_keys=ON")
    db.executescript("""
      CREATE TABLE IF NOT EXISTS signatures (
        signature_id TEXT PRIMARY KEY,
        company_id TEXT NOT NULL,
        signer_kind TEXT NOT NULL CHECK(signer_kind IN ('client','officer')),
        verified_signer_id TEXT NOT NULL,
        encrypted_signature BLOB NOT NULL,
        consent_reference TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending_sync',
        created_at INTEGER NOT NULL
      );
      CREATE TABLE IF NOT EXISTS phone_links (
        company_id TEXT NOT NULL,
        phone_hash TEXT NOT NULL,
        signature_id TEXT NOT NULL REFERENCES signatures(signature_id),
        PRIMARY KEY (company_id, phone_hash, signature_id)
      );
      CREATE TABLE IF NOT EXISTS sync_outbox (
        signature_id TEXT PRIMARY KEY REFERENCES signatures(signature_id),
        retry_count INTEGER NOT NULL DEFAULT 0,
        status TEXT NOT NULL DEFAULT 'queued'
      );
    """)
    db.commit()
    if dbpath.exists():
        os.chmod(dbpath, 0o600)
    return db

def phone_hash(value: str, vault_key: bytes) -> str:
    return hmac.new(vault_key, value.encode("ascii"), hashlib.sha256).hexdigest()

def register(args: argparse.Namespace) -> None:
    if not args.consent_reference.strip():
        raise ValueError("Explicit capture consent reference required")
    if not args.verified_signer_id.strip() or not args.company_id.strip():
        raise ValueError("Verified signer ID and company ID required")
    if args.signer_kind == "client" and not args.phones:
        raise ValueError("Client requires verified phone aliases")
    if args.signer_kind == "officer" and args.phones:
        raise ValueError("Officer identity must be resolved by authenticated user ID")
    phones = split_phones(args.phones) if args.phones else []
    raw = Path(args.capture_file).read_bytes()
    if not raw or len(raw) > 2_000_000:
        raise ValueError("Capture file must contain 1 to 2,000,000 bytes")
    # Capture-file contents must originate from trusted capture and signer verification.
    signature_id = secrets.token_hex(16)
    vault_key = key()
    encrypted = Fernet(vault_key).encrypt(raw)
    with connection() as db:
        db.execute("INSERT INTO signatures VALUES (?, ?, ?, ?, ?, ?, 'pending_sync', ?)",
                   (signature_id, args.company_id, args.signer_kind,
                    args.verified_signer_id, encrypted, args.consent_reference, int(time.time())))
        db.executemany("INSERT INTO phone_links VALUES (?, ?, ?)",
                       [(args.company_id, phone_hash(p, vault_key), signature_id) for p in phones])
        db.execute("INSERT INTO sync_outbox(signature_id) VALUES (?)", (signature_id,))
    print(json.dumps({"status":"stored_locally","signature_id":signature_id,
                      "sync_status":"queued","applied_to_contract":False}))

def resolve(args: argparse.Namespace) -> None:
    if not args.company_id.strip():
        raise ValueError("Company ID required")
    vault_key = key()
    with connection() as db:
        if args.signer_kind == "officer":
            if not args.verified_signer_id:
                raise ValueError("Officer requires authenticated verified signer ID")
            rows = db.execute("""SELECT signature_id, verified_signer_id FROM signatures
                WHERE company_id=? AND signer_kind='officer' AND verified_signer_id=?""",
                (args.company_id, args.verified_signer_id)).fetchall()
        else:
            aliases = split_phones(args.phones)
            marks = ",".join("?" for _ in aliases)
            rows = db.execute(f"""SELECT DISTINCT s.signature_id, s.verified_signer_id
                FROM signatures s JOIN phone_links p ON p.signature_id=s.signature_id
                WHERE s.company_id=? AND s.signer_kind='client' AND p.phone_hash IN ({marks})""",
                (args.company_id, *[phone_hash(p, vault_key) for p in aliases])).fetchall()
    ids = sorted({sid for sid, _ in rows})
    signers = {person for _, person in rows}
    if not ids:
        status = "not_found"
    elif len(ids) > 1 or len(signers) > 1:
        status = "conflict"
    else:
        status = "match"
    # A match is NOT an authorization to use the saved image on a contract.
    print(json.dumps({"status":status, "match_count":len(ids),
                      "signature_ids":ids if status == "match" else [],
                      "auto_apply":False, "requires_document_consent":True}))

def status(_args: argparse.Namespace) -> None:
    with connection() as db:
        count = db.execute("SELECT COUNT(*) FROM signatures").fetchone()[0]
        queued = db.execute("SELECT COUNT(*) FROM sync_outbox WHERE status='queued'").fetchone()[0]
    print(json.dumps({"service":"loanhub-signature-bridge","stored":count,
                      "queued":queued,"remote_sync_enabled":False,
                      "capture_adapter_enabled":False}))

def serve(_args: argparse.Namespace) -> None:
    global STOP
    connection().close()
    def shutdown(_signum, _frame):
        global STOP
        STOP = True
    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)
    print("Signature Bridge local vault ready; remote sync disabled.", flush=True)
    while not STOP:
        time.sleep(1)

def main() -> int:
    parser = argparse.ArgumentParser(description="LoanHub offline signature vault")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("serve")
    sub.add_parser("status")
    p = sub.add_parser("register")
    p.add_argument("--company-id", required=True)
    p.add_argument("--signer-kind", choices=("client","officer"), required=True)
    p.add_argument("--verified-signer-id", required=True)
    p.add_argument("--phones", default="")
    p.add_argument("--consent-reference", required=True)
    p.add_argument("--capture-file", required=True)
    p = sub.add_parser("resolve")
    p.add_argument("--company-id", required=True)
    p.add_argument("--signer-kind", choices=("client","officer"), default="client")
    p.add_argument("--verified-signer-id")
    p.add_argument("--phones", default="")
    args = parser.parse_args()
    try:
        {"serve":serve,"status":status,"register":register,"resolve":resolve}[args.command](args)
        return 0
    except (OSError, ValueError, RuntimeError, sqlite3.Error) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1

if __name__ == "__main__":
    raise SystemExit(main())
