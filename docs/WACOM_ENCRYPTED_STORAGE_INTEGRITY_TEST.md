# Wacom isolated encrypted-storage verification (Phase 13)

This work tests LoanHub's **existing file service**, not another Wacom
server process. Tests use a temporary storage directory, artificial PNG
bytes and a synthetic encryption key. Nothing is sent to production.

## What is tested

- Actual AES-GCM encryption before writing a synthetic test PNG to disk
- Stored bytes do **not** contain an accessible plaintext PNG
- Encrypted file metadata has nonce, version, SHA-256 and tenant ownership
- Existing `read_file_bytes` can decrypt and verify the original image
- Tampering with ciphertext causes an integrity-verification failure
- Scanner unavailable in fail-closed mode prevents storage
- Non-clean scan states are distinguishable from `clean`
- The Wacom capture API refuses to accept evidence when malware scanning
  is disabled

Run from LoanHub's existing backend working directory:

```bash
cd apps/backend
python -m pytest -q \
  tests/test_wacom_encrypted_storage_integrity.py \
  tests/test_wacom_png_validation.py \
  tests/test_local_signatures_api.py
```

## Important limits

The malware scanner is **mocked** in these tests; these tests do not prove
that a running ClamAV service works. Temporary local object storage
is real, but not the deployment's object storage backend. The tests
do not cover PostgreSQL RLS, key rotation, multi-company access or
real borrower consent.

Before real-API smoke testing, use an isolated LoanHub backend and actual
ClamAV with file encryption enabled, synthetic accounts, a dedicated
database and test-only file storage.

A clean-scanned, encrypted signature remains `pending_review` and cannot
sign any document without additional identity checks and explicit
document-specific authorization.
