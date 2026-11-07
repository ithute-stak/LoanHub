# Phase 18 — Isolated Compose blueprint for Wacom staging

**Blueprint only; do not launch it on a server hosting production until operations has explicitly verified isolation.** The overlay reuses LoanHub's existing FastAPI backend image and adds only a private ClamAV scanner. It is NOT a new Wacom connector on the VPS.

Files: `compose.yaml` and `compose.wacom-staging.yml`. Do not include `compose.edge.yml`, which joins a shared public edge network.

## Mandatory independent safeguards before any deployment

- Reserve a dedicated Docker daemon/host or security-reviewed, fully separate Compose project. Never use the production project's name, volumes, networks, secrets, images, database or credentials.
- Provision a fresh `.env.wacom-staging` file and a separately protected `staging-secrets/` directory; both must be excluded from version control. Do not copy production JWT private keys, file-encryption key, DB password, signing secrets or any real customer data.
- Set a unique `COMPOSE_PROJECT_NAME=loanhub-wacom-stage`, `LOANHUB_ENV_FILE=.env.wacom-staging`, `ENVIRONMENT=staging`, `DB_NAME=loanhub_wacom_staging`, unique `DB_USER`, `DB_PASSWORD`, `DB_RUNTIME_USER`, `DB_RUNTIME_PASSWORD`, `FILE_ENCRYPTION_KEY`, `FERNET_SECRET_KEY`, `SECRET_KEY`, and dedicated `BACKEND_BIND=127.0.0.1`, `BACKEND_PORT=18080`.
- Set `WACOM_TEST_ENVIRONMENT=ISOLATED`, `WACOM_TEST_ALLOWED_HOST` and `WACOM_TEST_API_ORIGIN` to the **actual dedicated test HTTPS origin**, only after approved TLS routing is installed.
- Audit existing LoanHub scheduled integrations and disable outgoing SMS, email, payments, treasury, payroll, collections and other side effects in the isolated deployment. The overlay disables a small subset; it is **not a comprehensive kill switch**.
- Inspect Docker Compose's fully resolved configuration and volume bindings before starting anything. Verify no `public-edge` network, no production secrets or volumes, and backend bound only to `127.0.0.1`.
- Validate the isolated deployment's security constraints and database migration privileges separately. The overlay does not automatically certify all services or database row-level security.

## Read-only configuration inspection

From a dedicated test checkout with staging secrets provisioned:

```bash
LOANHUB_ENV_FILE=.env.wacom-staging \
COMPOSE_PROJECT_NAME=loanhub-wacom-stage \
docker compose --env-file .env.wacom-staging \
  -f compose.yaml -f compose.wacom-staging.yml \
  config --quiet
```

Use `docker compose ... config` with care: **full output can contain secrets**. Do not paste or upload it. This example only validates the Compose model and does not start anything.

## Automated repository tests

```bash
cd apps/backend
python -m pytest -q tests/test_wacom_staging_compose_blueprint.py tests/test_wacom_staging_readiness.py
```

## Release gate

Once staging is genuinely isolated and the stacked PRs are reviewed/merged in order, use `docs/WACOM_REAL_LOANHUB_API_SMOKE.md` to validate the actual LoanHub HTTPS API with synthetic staff, company and borrower identities. Verify encrypted pending evidence, ClamAV rejection, independent review and audit. Do not enable real document signing.

Physical Wacom SDK and Go operator UI stay on the local workstation. All backend work uses the existing LoanHub API.

**Compose port-merge caution:** the staging overlay deliberately does not define `backend.ports` because Compose merges port lists additively. Set `BACKEND_BIND=127.0.0.1` and `BACKEND_PORT=18080` in the isolated test environment, then inspect the fully resolved Compose configuration with the Phase 19 gate. Never allow the default port 8000 to be published alongside 18080.
