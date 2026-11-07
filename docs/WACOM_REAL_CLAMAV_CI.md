# Wacom Phase 16 — real ClamAV scanning in CI

The LoanHub quality-gate workflow now starts an ephemeral official ClamAV
container bound to **127.0.0.1:33119 only**. The existing backend scanner
`scan_upload` communicates with the actual daemon via its INSTREAM protocol.

It verifies:
- A completely synthetic, valid PNG is scanned and reported `clean`.
- The standard **harmless EICAR anti-virus test signature** is detected,
  and the managed-file service responds with HTTP 422.
- Disconnecting the scanner from the test endpoint causes fail-closed
  behavior, with HTTP 503 rather than storing signature evidence.
- The daemon is stopped after the test step.

The test environment contains no real signatures, client identities,
documents or production data. The daemon is local to the CI runner and is
**not installed on the LoanHub VPS**.

CI: `apps/backend/tests/test_wacom_real_clamav.py` executes with
`WACOM_REAL_CLAMAV_HOST=127.0.0.1` and
`WACOM_REAL_CLAMAV_PORT=33119`. Without both values the tests skip. The
workflow provides both values so CI must execute them rather than silently
skipping. The CI job fails when the container cannot start or a scanner
test fails.

This completes **test coverage of the scanner protocol** but does not
prove test-VPS ClamAV deployment, PostgreSQL RLS, full physical browser
capture, document-specific consent or final signing. Those remain
independent gated milestones.
