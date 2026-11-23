# Data Center staging browser probe (read-only)

This is an **opt-in real Chromium browser probe**, not a certification pass and not a production deployment. The probe opens **two independent Playwright browser contexts**, each using a different pre-provisioned synthetic account's storage state, and verifies:
- WebSocket connection observed in each independent context
- The opt-in Data Center bridge requests an authenticated snapshot
- The snapshot reports a complete, replay-capable projection for the expected synthetic company
- Reload opens a new WebSocket and fetches a fresh authorized snapshot

It **does not** verify event delivery, financial mutations, missed-event replay, logout/company switching or security revocation, and must not be used to authorize capture. Execute the RB-01 through RB-12 matrix in `docs/data-center/real-browser-certification-gate.md` separately.

## Preconditions

- A separately configured staging deployment built with `NEXT_PUBLIC_LOANHUB_DATA_CENTER_ENABLED=true` and server capture **only for the isolated synthetic test company**, after explicit authorization. Do not change the public production build or Batlokoa capture.
- Two independent owner/admin test accounts authorized only for that synthetic company, each logged in using a separate Playwright browser context. Keep their `storageState` JSON files outside git and protected by filesystem permissions.
- A temporary, approved staging address with HTTPS and a functioning `/ws` route.
- Locally installed Playwright and Chromium. From the repo root, use `npm install --no-save playwright` only in an isolated test checkout, followed by `npx playwright install chromium`. No CI or production dependency is added.
- A testing operator available to review output. The probe contains no synthetic data writes.

## Execute

```bash
LOANHUB_E2E_BASE_URL=https://your-authorized-staging-host.example \
LOANHUB_E2E_STATE_A=/secure/synthetic-a.json \
LOANHUB_E2E_STATE_B=/secure/synthetic-b.json \
LOANHUB_E2E_COMPANY_ID=your-synthetic-company-id \
node apps/frontend/tests/data-center-staging-browser-probe.mjs
```

A passing read-only probe is only preliminary evidence; run the complete browser certification matrix before approving a pilot. Do not copy cookies, bearer tokens, national IDs, client rows, or snapshots into issues or CI logs.
