# Batlokoa signed collection-preview staging verification

**Scope:** read-only, non-posting integration. This runbook does not authorize
live payment collection, payout, shared custody, platform fee enforcement,
provider credential issuance, or database migrations.

## Prerequisites

- LoanHub and IthutePay releases must contain the merged signed preview code.
- Run first against isolated staging services with test borrower/loan fixtures,
  not real customer records.
- Preserve the currently functioning production signed GET handshake.
- Keep both production preview gates disabled:
  - LoanHub: `ITHUTEPAY_BATLOKOA_INTENT_PREVIEW_ENABLED=false`
  - IthutePay: `LOANHUB_BATLOKOA_INTENT_PREVIEW_ENABLED=false`
- Never log the HMAC secret, nonce values, borrower PII or signed headers.
- Do not enable payment/payout routing, idempotency reservation, shared custody
  or financial postings.

## Phase 1: read-only production verification

On the production VPS, check container state and that no preview flag is enabled.
These commands print **boolean state only**, not secret contents.

```bash
sudo docker exec -i -w /app loanhub-backend-1 python - <<'PY'
from database.config.config import settings
assert not settings.ITHUTEPAY_BATLOKOA_INTENT_PREVIEW_ENABLED, "STOP: LoanHub preview enabled"
print("LoanHub preview: DISABLED")
PY

sudo docker exec -i -w /app/backend ithute-pay-ithute-pay-bridge-1 python - <<'PY'
from database.config.config import settings
assert not settings.LOANHUB_BATLOKOA_INTENT_PREVIEW_ENABLED, "STOP: IthutePay preview enabled"
print("IthutePay preview: DISABLED")
PY
```

If either assertion fails, stop. Do not change flags automatically.

The signed handshake verification command is a read-only production sanity
check and must be run only in an approved maintenance session:

```bash
sudo docker exec -i -w /app loanhub-backend-1 \
  python -m scripts.verify_batlokoa_ithutepay_handshake
```

## Phase 2: staging with explicitly approved, synthetic data only

1. Confirm staging hostname, TLS, access restrictions, independent secrets,
   isolated PostgreSQL and Redis, and corresponding image digests.
2. Verify absent flag returns HTTP 404 on the IthutePay signed preview route.
3. Verify malformed/unsigned signature returns HTTP 401 with the feature enabled.
4. Verify forged body, expired timestamp and repeated nonce return HTTP 401.
5. Verify well-signed request for the wrong company returns HTTP 401.
6. Verify approved synthetic Batlokoa loan & authorized staff yields a non-posting
   preview containing the expected request fingerprint.
7. Verify a borrower, a cross-company staff member, branch-mismatched staff,
   undisbursed loan, closed loan and over-balance amount fail closed.
8. Confirm the same idempotency key is **not reserved** and no payment
   transaction, ledger, provider callback, fee or settlement is created.
9. Confirm simulated Redis outage causes denial, not bypass.
10. Compare pre/post database record counts and system audit logs, and retain
    redacted evidence in the staging release report.

## Rollback

- Disable both preview gates in staging.
- Roll back the staging image digests only through the established, approved
  deployment mechanism.
- Do not alter existing M-PESA provider configuration or shortcode 38542.
- Do not delete Docker volumes, database rows or replay keys as rollback.
- Verify the original signed GET handshake still works.

## Release decision

GitHub CI success is necessary but not sufficient for deployment. Require
independent staging security tests, DBA signoff on tenant isolation, audit
evidence, financial review and an explicit go/no-go approval. A preview
response is never payment authority or permission to debit a borrower.
