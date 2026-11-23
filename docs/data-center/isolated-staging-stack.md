# Data Center isolated certification stack — preparation only

This stack is **not deployed automatically**. It is **not a certified pilot** and must never be composed together with production `compose.yaml`. It has its own Docker Compose project, internal service network, PostgreSQL and Redis, private signing keys and host-loopback bindings. It does not restore or mount production customer data.

## Before starting

1. Use a dedicated, secured staging hostname and API hostname with TLS. Obtain approval for the staging endpoint and its reverse-proxy rules. Keep both off `loanhub.co.ls`, `api.loanhub.co.ls` and Batlokoa production.
2. Prepare `.env.dc-staging` with **fresh**, non-production credentials and the following required variables:
   - `DC_CERT_DB_PASSWORD` — randomly generated strong password, never production's
   - `DC_CERT_APP_ORIGIN` — staging frontend HTTPS origin
   - `DC_CERT_API_URL` — staging backend HTTPS URL ending `/api/v1`
   - Any other mandatory non-production backend environment variables, with integrations/payment/disbursement/notifications **disabled** or pointed at test-only endpoints
3. Create `dc-cert-secrets/jwt_private.pem` and `dc-cert-secrets/jwt_public.pem` as a **new** signing keypair, never reused from production, generated using the backend's documented accepted key algorithm. Keep them outside version control.
4. Ensure the reverse proxy routes only the staging hostnames to `127.0.0.1:38101` (web) and `127.0.0.1:38100` (API including WebSocket upgrade); enforce HTTPS and access restrictions. The compose file intentionally **does not** publish a public service.
5. Ensure there are no port conflicts, the deployment host has headroom, and an operator can monitor the separate stack. A separate VPS is preferable to avoid resource contention with financial production.
6. Run `python3 scripts/data-center-cert-preflight.py`. **A PASS only checks local configuration.** Validate all routes, outbound integrations, and data isolation separately before any launch.
7. If approved, review the fully rendered `docker compose -f compose.dc-cert.yml --project-name loanhub-dc-cert config` in a secure environment; note that the rendering may include secret values and must never be pasted into CI logs.
8. Only after an explicit deployment decision, use `docker compose -f compose.dc-cert.yml --project-name loanhub-dc-cert up -d --build` from a clean, isolated checkout. Do not use `pull loanhub latest` or merge with production compose.

## Important limitations

- The staging **frontend** is built with `NEXT_PUBLIC_LOANHUB_DATA_CENTER_ENABLED=true`, while the normal frontend Dockerfile defaults it to `false`. This is a public build-time toggle, **not** authorization. The backend must still authorize scopes and enable capture solely for a synthetic company under a separately approved pilot configuration.
- This compose topology is a staging *candidate*, not an executable proof of all required environment variables, migrations, seed accounts, key formats, outbound integrations or reverse-proxy setup. Those must be verified before use.
- The database starts empty and is not automatically seeded. The operator must create a **synthetic** company and two owner/admin test accounts using safe existing enrollment mechanisms.
- The standalone read-only Chromium probe is at `apps/frontend/tests/data-center-staging-browser-probe.mjs`; its instructions are in `docs/data-center/staging-browser-probe.md`. Its PASS alone does **not** certify event delivery, tenant switching, revoked sessions or recovery of missed changes.
- Run the full 12-case matrix in `docs/data-center/real-browser-certification-gate.md`. Do not enable real Batlokoa capture before all cases pass and an authorized owner signs off.
- Never copy production PostgreSQL backups, customer PII, payment credentials, JWT keys or uploaded files into staging.

## Safe removal (only after verifying the Compose project)

Use `docker compose -f compose.dc-cert.yml --project-name loanhub-dc-cert down` to stop containers. Removing volumes (`down -v`) destroys staging data and requires explicit authorization; do not run it as a routine cleanup.
