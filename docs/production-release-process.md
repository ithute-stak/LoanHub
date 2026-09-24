# LoanHub production release process

LoanHub production is operator-controlled. GitHub must never SSH into the production VPS or change a running production service automatically.

## Release flow

1. Merge tested application changes into `main`.
2. `LoanHub CI` must complete successfully.
3. `LoanHub Release Images` publishes the backend and frontend images to GHCR using the exact tested commit SHA as the image tag.
4. Confirm the release-image workflow is green. A green CI run without a green release-image run is not a deployable release.
5. Log into the production VPS manually.
6. Authenticate Docker to GHCR if the VPS is not already authenticated.
7. Run the manual production deployment helper with either the exact 40-character SHA or the guarded `latest` selector.
8. Confirm the helper reports healthy backend/frontend containers and successful public API/web checks.

GitHub Actions does not deploy to the VPS. The production system remains on its current release until an operator explicitly performs step 7.

## One-time VPS setup

Keep the checked-in helper at `/opt/loanhub/scripts/deploy-production-manual.sh` and make it executable:

```bash
chmod 700 /opt/loanhub/scripts/deploy-production-manual.sh
```

The VPS must already contain the existing production state, including:

- `/opt/loanhub/.env.production`
- `/opt/loanhub/compose.yaml`
- `/opt/loanhub/compose.edge.yml`
- `/opt/loanhub/secrets/jwt_private.pem`
- `/opt/loanhub/secrets/jwt_public.pem`
- the external Docker network `public-edge`

## GHCR login

Authenticate the VPS to GitHub Container Registry using a token that has permission to read the LoanHub packages. Do not place the token in this repository or in shell history.

```bash
docker login ghcr.io -u <github-username>
```

Enter the token when Docker prompts for the password.

## Deploy a tested release

Use the exact SHA shown by the successful `LoanHub Release Images` workflow:

```bash
cd /opt/loanhub
./scripts/deploy-production-manual.sh <40-character-release-sha>
```

Or ask the helper to select the newest successful release-image run that is a forward descendant of the release currently recorded in `/opt/loanhub/releases/current.sha`:

```bash
cd /opt/loanhub
./scripts/deploy-production-manual.sh latest
```

The `latest` selector is deliberately fail-closed. It skips stale, behind, and diverged commits, requires both immutable GHCR images to exist, and will not auto-select a release if the current production SHA is unknown.

Before any migration is attempted, the helper also checks that the candidate backend image contains every Alembic revision currently recorded by the live database. This prevents an older image from being applied to a database that has already moved past that image's migration history.

The migration is executed with its real container exit code. If Alembic fails, the deployment stops before backend/frontend replacement. PostgreSQL and Redis remain persistent, and the current application release is left in place.

For a valid forward release, the helper pulls both immutable SHA-tagged images, verifies the existing production state, starts PostgreSQL/Redis, creates a PostgreSQL backup, applies Alembic migrations, restarts backend/maintenance/frontend, verifies container health, and checks the public web/API endpoints.

The successful release SHA is recorded at `/opt/loanhub/releases/current.sha`; the previous SHA is retained at `/opt/loanhub/releases/previous.sha` when available.

## Important rules

Do not deploy merely because a commit exists on `main`. Deploy only a SHA for which both `LoanHub CI` and `LoanHub Release Images` completed successfully.

Normal deployment is forward-only. A database-backed production rollback is a separate recovery operation and must not be simulated by deploying an older application SHA over a newer schema.
