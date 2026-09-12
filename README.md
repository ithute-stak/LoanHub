Important rule

Run these only on the PC:

git add .
git commit
git push

Run these on the VPS to deploy updates:

git fetch origin
git reset --hard origin/main

Never store GitHub personal access tokens in this repository. Supply registry credentials through environment variables or GitHub Actions secrets instead:

```bash
echo "$GITHUB_TOKEN" | docker login ghcr.io -u "$GITHUB_USERNAME" --password-stdin
```

# LoanHub

**LoanHub** is a multi-tenant loan management and loan-marketplace platform for Lesotho. The product identity uses the LoanHub icon and horizontal logo. **Ithute Solutions** is the software developer and maintenance brand and is credited separately in the application, source documentation and generated reports.

## Product capabilities

- Platform-owner governance of companies, subscriptions, payments, incidents and system configuration
- Isolated company tenants with branches and role-based access
- Borrower loan-request broadcasting and competitive lender offers
- Loan products, approvals, disbursements, schedules, repayments and collections
- Employee call tracking, controlled WebRTC/SIP calling, recording retention, listen-only supervision and quality assurance
- Persistent realtime notifications and complete CRUD audit history
- Employee records, performance goals, reviews and branch/company/platform analytics
- Double-entry accounting foundation
- Daily, weekly, monthly and annual PDF/CSV reporting
- WhatsApp-style internal chat with presence, voice notes and managed attachments
- Encrypted-at-rest chat text and managed files using AES-GCM
- Light, dark and system themes
- Time-limited, audited platform-owner role switching for support and workflow testing
- Docker Compose deployment with PostgreSQL, Redis, FastAPI, Next.js and maintenance services; reverse-proxy configuration is maintained separately under `infra/caddy/`.

## Repository layout

```text
apps/backend/      FastAPI, SQLAlchemy, Alembic, workers and report generation
apps/frontend/     Next.js, React, Redux, realtime providers and role portals
apps/call_mobile/  Flutter employee call-tracking and controlled-calling client
brand/             Product logos and the separate Ithute Solutions developer logo
docs/              Architecture, deployment, security and role documentation
infra/caddy/       HTTPS reverse-proxy configuration
scripts/           Validation and Hostinger deployment scripts
secrets/           Local deployment key location; never commit private keys
compose.yaml       Core application stack
```

## Branding rules

- `loanhub-app-icon.png`: application icon, favicons and compact navigation
- `loanhub-horizontal-logo.png`: login, public pages, reports and product headers
- `ithute-solutions-developer-logo.png`: small developer/maintenance credit only

Do not present the Ithute Solutions logo as the LoanHub product logo.

## Security statement

Chat messages and managed files are encrypted **at rest** with authenticated AES-GCM encryption. Production traffic should be protected by HTTPS/WSS through the supplied reverse-proxy configuration. This is not client-to-client end-to-end encryption: the authorised LoanHub server can decrypt content to enforce access, deliver files and support business workflows.

Ordinary users never receive stack traces or technical exception objects. Unhandled incidents are grouped, stored and broadcast only to active platform owners. The affected user receives a generic message and request reference.

Call recording is designed only for authorised company business communications. Reliable recording and live monitoring require the controlled WebRTC/SIP media path and company policy; the mobile app does not attempt to capture both sides of arbitrary Android cellular calls.

## Quick start

```bash
cp .env.example .env
mkdir -p secrets
# Add JWT private/public PEM files described in secrets/README.md
docker compose up -d --build
```

Create the first platform owner:

```bash
docker compose exec backend python scripts/create_superadmin.py \
  --phone 58000000 \
  --email owner@example.com \
  --first-name Platform \
  --last-name Owner
```

The optional `scale-out` profile uses MinIO and requires an explicit `MINIO_ROOT_PASSWORD` in `.env`; do not deploy it with placeholder credentials.

## Migration policy

Current Alembic head:

```text
c3s6t8u0v134
```

Always back up PostgreSQL, stop competing database users, and use the dedicated `migrate` service. Never use `alembic stamp head` to hide a failed migration. Do not create meaningless `test` revisions.

## Validation

Install backend development/test dependencies in addition to runtime dependencies when validating locally:

```bash
python -m pip install -r apps/backend/requirements.txt -r apps/backend/requirements-dev.txt
corepack enable
pnpm --dir apps/frontend install --frozen-lockfile
./scripts/validate_project.sh
```

The GitHub workflow runs secret scanning, static security analysis, backend compilation and pytest, validates the Alembic migration graph, checks accounting integrity, performs a PostgreSQL backup/restore drill, runs frontend type checking/linting/building, executes browser/API E2E checks, validates Docker Compose, and smoke-builds the production image before publishing.

The Flutter employee client lives under `apps/call_mobile`. See its README before generating the Android platform shell and release APK.

## Deployment

See `docs/HOSTINGER_GITHUB_DEPLOYMENT.md`. A push to `main` can validate the release in GitHub Actions and then publish the production image after all quality gates pass. The GHCR namespace follows the current GitHub repository owner so repository transfers do not leave deployments pointing at a stale account.

Call management deployment additionally requires LiveKit/WebRTC server credentials and a company-approved SIP provider/trunk before real PSTN calls are enabled. See `docs/CALL_MANAGEMENT_INTEGRATION.md`.

## Important production limitations

- Live M-Pesa calls are routed through IthutePayBridge. Each LoanHub company supplies only its M-Pesa business shortcode; PayBridge owns the provider credentials, Origin, callback and SessionKey configuration. Vodacom must authorise the PayBridge application to operate each company shortcode before live use.
- Live EcoCash calls still require official merchant onboarding, provider credentials, callback verification, transaction enquiry, reversal, reconciliation and certification.
- Controlled call recording/live monitoring require provisioned WebRTC/SIP infrastructure, company policy and the appropriate notice/consent process. Ordinary Android SIM-call recording is not treated as a reliable supported path.
- The accounting module is a double-entry foundation and should be reviewed by a qualified accountant.
- Local Docker media volumes are suitable for one VPS. Multi-server deployment should use S3/MinIO-compatible object storage and malware scanning.
