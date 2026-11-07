# Wacom real LoanHub API smoke test — isolated environment only

This is the **first actual HTTPS backend smoke-test harness**. Unlike the Go
`httptest` integration tests, it targets a running LoanHub FastAPI instance
with normal authentication, tenant permissions, encryption and file storage.
It requires an **isolated, explicitly authorized test environment**. It does
not install a Wacom bridge on the VPS.

The previous GitHub CI proved that the PC's software protocol behaves
correctly against a simulated API. Separately, the physical Wacom STU-540
captured 231 pen reports and generated a PNG on the PC. Neither result proves
that the actual LoanHub test database and storage work end to end.

## Before running

- Deploy approved backend code to a **separate LoanHub test environment**
  using isolated test database, isolated storage, and real encryption keys.
- Verify malware scanning is enabled and configured to fail closed.
- Provision an expressly synthetic staff account with an active tenant
  membership; configure one synthetic borrower with a National ID beginning
  `TEST-` if exercising lookup.
- Do **not** use production credentials, any existing customer or operator,
  or a production LoanHub API origin.
- Observe this environment's access/audit logs and clear the synthetic
  captures after testing.

## Run unauthenticated checks only (safe default)

```bash
cd apps/backend
export WACOM_TEST_ENVIRONMENT=ISOLATED
export WACOM_TEST_ALLOWED_HOST=loanhub-api-test.example
python3 scripts/wacom_real_api_smoke.py \
  --origin=https://loanhub-api-test.example
```

The hostname is an **example placeholder**, not a live endpoint. Configure
the actual isolated deployment hostname before running. The script verifies
that protected capture/status and review endpoints refuse unauthenticated
requests. No credentials, client IDs or signatures are sent.

## Authenticate a synthetic staff account

```bash
export WACOM_TEST_COMPANY_ID="YOUR_TEST_COMPANY_UUID"
export WACOM_TEST_PHONE="YOUR_SYNTHETIC_STAFF_PHONE"
read -rs -p 'Synthetic test password: ' WACOM_TEST_PASSWORD
echo
export WACOM_TEST_PASSWORD

python3 scripts/wacom_real_api_smoke.py \
  --origin=https://loanhub-api-test.example \
  --authenticated
unset WACOM_TEST_PASSWORD
```

For MFA, provide `WACOM_TEST_OTP` by the same non-echoing process. This
checks an actual login and scoped operator signature status, but does not
capture anything.

## Optional synthetic borrower lookup

Provision a fictional test borrower with a `TEST-` National ID. Then run
`--authenticated --lookup` with `WACOM_TEST_NATIONAL_ID` set to that ID.
Never use a real National ID. The script reports only pass/fail, not personal
details.

## Optional synthetic test PNG upload

**Only in the isolated test environment**, and only after approving its
temporary, non-contract test evidence lifecycle, set
`WACOM_TEST_UPLOAD=YES` and run
`--authenticated --upload-operator-test`. The script generates an empty
synthetic PNG, not any Wacom handwriting. It verifies an actual HTTP 202
pending-review receipt. It does not use a borrower ID, approve the capture,
sign a loan, or delete any data. Remove the test evidence through the
approved administrative cleanup process afterwards.

## Mandatory next checks before production

- Separate two-user evidence review and audit chain
- Real tenant/branch access and cross-tenant rejection
- Encryption at rest, ClamAV scanning, backup and recovery
- Duplicate upload and network interruption behavior
- Review-image privacy and revocation
- Real physical PC browser initiated capture, not just CLI diagnostic
- Fresh contract-bound borrower consent and atomic signing operation

No real signatures should be used until these checks pass and the legal/
security approval process is complete.
