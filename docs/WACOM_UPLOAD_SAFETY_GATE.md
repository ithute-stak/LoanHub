# Wacom signature upload hardening — preflight for real API tests

Before running controlled tests against the real LoanHub FastAPI backend,
this change closes two signature-evidence ingestion gaps:

1. A PNG header and SHA-256 checksum are **not enough** to establish that
   the image is a valid, bounded PNG. The API now checks the full chunk
   layout and CRCs, image dimensions, supported pixel formats, compressed
   image payload, expected decoded scanline lengths and maximum expansion.
   Metadata and animated chunks are rejected.
2. Signature evidence now requires encryption and **enabled, fail-closed
   malware scanning**. A capture is not acknowledged as pending review
   unless the stored file is encrypted and has scan status `clean`.

These checks apply only to Wacom signature evidence, not ordinary LoanHub
file uploads. No existing M-PESA, IthutePay, lending or PDF services are
changed. No Wacom capture service is installed on the VPS.

## Test commands

```bash
cd apps/backend
python -m pytest -q \
  tests/test_wacom_png_validation.py \
  tests/test_local_signatures_api.py \
  tests/test_wacom_real_api_smoke.py
```

Do not run authenticated or upload-capable real-API smoke testing until the
existing LoanHub backend is deployed to an approved **isolated**
test environment with test-only company, staff and borrower records,
working encryption keys, ClamAV clean scanning and an approved test
data-cleanup procedure.

Signature review still does not authorize contract signing.
