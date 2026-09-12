# LoanHub production deployment: Cloudflare DNS + Ubuntu VPS + GHCR

LoanHub production uses one Ubuntu VPS and a Dockerized application stack:

- `https://loanhub.co.ls` — Next.js frontend
- `https://api.loanhub.co.ls` — FastAPI backend
- `https://www.loanhub.co.ls` — permanent redirect to `https://loanhub.co.ls`
- PostgreSQL 16 — Docker-only private service with persistent named volume
- Redis 7 — Docker-only private service with persistent named volume
- Caddy — the only public web entry point on ports 80/443; obtains and renews HTTPS certificates automatically

The production release flow mirrors the Lelefa Debt Collectors deployment model: GitHub Actions validates the application first, builds immutable backend/frontend images, publishes them to GitHub Container Registry (GHCR), then connects to the VPS and pulls those images. The VPS never needs to compile the production application during a normal release.

## 1. Cloudflare DNS

For the current LoanHub VPS (`204.12.205.224`) use:

| Type | Name | Value |
| --- | --- | --- |
| A | `@` | `204.12.205.224` |
| A | `api` | `204.12.205.224` |
| CNAME | `www` | `loanhub.co.ls` |

Keep the records DNS-only while performing first certificate issuance. Cloudflare proxying can be enabled after direct HTTPS is verified.

Do not expose PostgreSQL, Redis, port 3000 or port 8000 directly to the internet.

## 2. One-time Ubuntu VPS preparation

Use Ubuntu 24.04 LTS. Allow inbound SSH (`22/tcp`), HTTP (`80/tcp`) and HTTPS (`443/tcp`). UDP 443 is optional for HTTP/3.

Install Docker Engine, Docker Compose, Git, curl, OpenSSL and Python 3. Use the non-root `administrator` account with Docker group access and SSH keys.

Create the deployment path:

```bash
sudo mkdir -p /opt/loanhub
sudo chown administrator:administrator /opt/loanhub
```

Clone the repository once so the production preparation helpers are available:

```bash
git clone https://github.com/Lelefe-dc/LoanHub.git /opt/loanhub
cd /opt/loanhub
```

Prepare private production configuration and JWT keys:

```bash
bash ./scripts/prepare_production_env.sh your-real-email@example.com
```

This creates `.env.production` and `secrets/jwt_private.pem` / `secrets/jwt_public.pem`. Never commit those files.

The generated production environment includes:

```dotenv
LOANHUB_BACKEND_IMAGE=ghcr.io/lelefe-dc/loanhub-backend
LOANHUB_FRONTEND_IMAGE=ghcr.io/lelefe-dc/loanhub-frontend
LOANHUB_IMAGE_TAG=latest
APP_DOMAIN=loanhub.co.ls
API_DOMAIN=api.loanhub.co.ls
WWW_DOMAIN=www.loanhub.co.ls
PUBLIC_APP_URL=https://loanhub.co.ls
CORS_ORIGINS=https://loanhub.co.ls
NEXT_PUBLIC_API_URL=https://api.loanhub.co.ls/api/v1
```

Run the preflight once:

```bash
bash ./scripts/production_preflight.sh
```

## 3. GitHub Actions secrets

Repository Actions secrets required for automatic VPS deployment:

- `VPS_USER` — normally `administrator`
- `VPS_SSH_KEY` — private key corresponding to a public key in the VPS user's `~/.ssh/authorized_keys`
- `VPS_SSH_PASSPHRASE` — optional; only required if the deployment key is encrypted
- `VPS_APP_DIR` — `/opt/loanhub`
- `GHCR_USERNAME` — GitHub account permitted to read the private LoanHub packages
- `GHCR_TOKEN` — GitHub token with package read permission for the VPS pull

The VPS hostname is currently configured in the workflow as `204.12.205.224`.

Do not store the VPS login password, `.env.production`, JWT private key, database password, payment credentials or other production application secrets in the repository.

## 4. Release pipeline

A pull request to `main` runs the full quality gate but does not publish or deploy.

A push/merge to `main` runs, in order:

1. Secret scanning and static security checks.
2. Backend compilation and complete pytest suite.
3. Alembic migration-graph validation on Dockerized PostgreSQL.
4. Accounting integrity and PostgreSQL backup/restore drill.
5. Frontend typecheck, lint and production build.
6. Browser/API E2E and DAST smoke checks.
7. Docker Compose/script validation.
8. Backend and frontend production Docker smoke builds.
9. Publish `ghcr.io/lelefe-dc/loanhub-backend:latest` and `:<commit-sha>`.
10. Publish `ghcr.io/lelefe-dc/loanhub-frontend:latest` and `:<commit-sha>`.
11. Copy the current `compose.yaml` and Caddyfile to the VPS.
12. Pull the exact commit-SHA images on the VPS.
13. Start Dockerized PostgreSQL/Redis and create a pre-migration PostgreSQL dump.
14. Run Alembic with the just-published backend image.
15. Start backend, frontend, maintenance and Caddy with `--no-build`.
16. Verify container health and public HTTPS endpoints.

If any quality gate fails, images are not published and the VPS is not touched. If image publishing fails, deployment does not start.

## 5. Dockerized PostgreSQL

PostgreSQL is part of `compose.yaml`:

```text
postgres:16-alpine
  -> private Docker network
  -> postgres_data named volume
  -> no public host port
```

The application reaches PostgreSQL as `db:5432`. Database contents survive application image upgrades because the data lives in the persistent `postgres_data` volume rather than inside an application container.

Every automated release creates a custom-format PostgreSQL backup in `/opt/loanhub/backups` before Alembic migrations are applied.

## 6. Manual release

Automatic GitHub deployment is preferred. If a manual release is needed after authenticating Docker to GHCR:

```bash
cd /opt/loanhub
./scripts/deploy_hostinger.sh
```

That script now pulls the configured GHCR backend/frontend images instead of compiling them on the VPS, backs up PostgreSQL, applies migrations and verifies HTTPS health.

## 7. Verification and diagnostics

```bash
curl -I https://loanhub.co.ls
curl https://api.loanhub.co.ls/health/ready
curl -I https://www.loanhub.co.ls
```

Container status and logs:

```bash
cd /opt/loanhub
docker compose --env-file .env.production --profile production ps
docker compose --env-file .env.production --profile production logs --tail=200 caddy backend frontend db redis
```

Direct external access to ports 3000, 8000, 5432 and 6379 is not required and should remain blocked.

## 8. Rollback

Each release publishes a commit-SHA tag. To roll back application code, set `LOANHUB_IMAGE_TAG` in `.env.production` to a known-good commit SHA, pull the backend/frontend services, then run the production stack with `--no-build`.

Database downgrades are not automatic. If a release introduced a migration that cannot safely be reversed, restore the matching pre-release PostgreSQL dump from `/opt/loanhub/backups` after stopping application traffic.
