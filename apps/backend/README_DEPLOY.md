# LoanHub FastAPI — Docker deployment on Hostinger VPS

This bundle is designed to be copied into the root of the **latest** FastAPI
backend. It provides:

- FastAPI container
- PostgreSQL 16 container with persistent storage
- automatic Alembic migrations on API startup
- Caddy reverse proxy with automatic HTTPS
- private Docker network for API and PostgreSQL
- database health checks
- database backup and restore scripts
- fresh JWT-key generation

## 1. Copy the bundle into the current backend

Copy these files and directories into the root of the current backend:

```text
Dockerfile
compose.yaml
requirements.txt
.env.example
.dockerignore
.gitignore
caddy/
docker/
scripts/
```

The `patches/` directory contains recommended replacement files. Review and
merge them into the current application:

```text
patches/main.py                       -> main.py
patches/database/config/config.py    -> database/config/config.py
patches/alembic/env.py               -> alembic/env.py
patches/database/base.py             -> database/base.py
```

Do not overwrite newer business models, routers, schemas, or migrations with
files from an older ZIP.

## 2. Test locally before uploading

From the backend root:

```bash
cp .env.example .env
./scripts/generate_secrets.sh --rotate
```

Edit `.env` and at minimum set:

```dotenv
API_DOMAIN=api.yourdomain.com
TLS_EMAIL=you@yourdomain.com
CORS_ORIGINS=https://yourdomain.com,http://localhost:3000
DB_PASSWORD=a-long-random-password
```

For a local test without DNS/Caddy, temporarily expose the API by adding this
under the `api` service in a local-only override file:

```yaml
services:
  api:
    ports:
      - "8000:8000"
```

Then:

```bash
docker compose up -d --build db api
docker compose logs -f api
```

Test:

```bash
curl http://localhost:8000/health
```

Remove the local port override before production.

## 3. Prepare Hostinger VPS

Use a fresh Ubuntu 24.04 VPS or Hostinger's Docker template. Changing the OS
or applying a new template can erase existing VPS data, so back up first.

Point the chosen API subdomain to the VPS IPv4 address:

```text
Type: A
Name: api
Value: YOUR_VPS_IP
```

Open only these inbound TCP ports in Hostinger's VPS firewall:

```text
22   SSH
80   HTTP / certificate issuance
443  HTTPS
```

Do not open PostgreSQL port 5432 or FastAPI port 8000 publicly.

## 4. Connect and install Docker

```bash
ssh root@YOUR_VPS_IP
```

If the Docker template is already installed, verify:

```bash
docker version
docker compose version
```

Otherwise install Docker Engine and the Compose plugin from Docker's official
Ubuntu repository.

## 5. Create a non-root deployment user

```bash
adduser deploy
usermod -aG sudo,docker deploy
mkdir -p /home/deploy/.ssh
cp /root/.ssh/authorized_keys /home/deploy/.ssh/authorized_keys
chown -R deploy:deploy /home/deploy/.ssh
chmod 700 /home/deploy/.ssh
chmod 600 /home/deploy/.ssh/authorized_keys
```

Reconnect:

```bash
ssh deploy@YOUR_VPS_IP
```

## 6. Upload or clone the backend

Recommended:

```bash
cd /opt
sudo mkdir -p loanhub/backend
sudo chown -R deploy:deploy loanhub
cd loanhub/backend
git clone YOUR_PRIVATE_REPOSITORY_URL .
```

Alternatively, upload with SFTP or `scp`.

## 7. Configure production secrets

```bash
cp .env.example .env
./scripts/generate_secrets.sh --rotate
nano .env
```

Set real values for:

```dotenv
API_DOMAIN=api.yourdomain.com
TLS_EMAIL=you@yourdomain.com
CORS_ORIGINS=https://your-frontend-domain.com
DB_PASSWORD=use-a-long-random-password
```

Never commit `.env`, database backups, or JWT private keys.

## 8. Confirm Alembic before first production startup

The migration graph must have one head:

```bash
docker compose build api
docker compose run --rm api alembic heads
docker compose run --rm api alembic history
```

Resolve multiple heads or broken migrations before proceeding.

## 9. Deploy

```bash
./scripts/deploy.sh
```

Watch logs:

```bash
docker compose logs -f api
docker compose logs -f caddy
```

Check status:

```bash
docker compose ps
```

After DNS has propagated and ports 80/443 are reachable, Caddy will obtain and
renew the HTTPS certificate automatically.

## 10. Verify

```bash
curl https://api.yourdomain.com/health
curl https://api.yourdomain.com/
```

Swagger UI:

```text
https://api.yourdomain.com/docs
```

## 11. Import an existing local database

Create a dump locally:

```bash
pg_dump \
  --host localhost \
  --username YOUR_LOCAL_DB_USER \
  --dbname YOUR_LOCAL_DB_NAME \
  --format custom \
  --no-owner \
  --no-privileges \
  > loanhub.dump
```

Upload it into `backups/` on the VPS, then restore:

```bash
./scripts/restore_db.sh backups/loanhub.dump
```

Run migrations after restoring:

```bash
docker compose run --rm api alembic upgrade head
```

## 12. Backups

Manual backup:

```bash
./scripts/backup_db.sh
```

Example daily cron at 02:15:

```bash
crontab -e
```

```cron
15 2 * * * cd /opt/loanhub/backend && ./scripts/backup_db.sh >> /var/log/loanhub-backup.log 2>&1
```

Copy backups to a separate machine or object-storage provider. A backup stored
only on the VPS is not sufficient protection against disk loss.

## 13. Update the application

```bash
./scripts/update.sh
```

The update script creates a backup, pulls the current Git branch, rebuilds the
API, applies migrations on startup, and removes unused images.

## 14. Useful commands

```bash
# All services
docker compose ps

# API logs
docker compose logs -f --tail=200 api

# Caddy / TLS logs
docker compose logs -f --tail=200 caddy

# PostgreSQL logs
docker compose logs -f --tail=200 db

# Run a migration command
docker compose run --rm api alembic current

# Open a PostgreSQL shell
docker compose exec db psql -U "$DB_USER" -d "$DB_NAME"

# Restart only the API
docker compose restart api

# Stop the stack without deleting data
docker compose down

# Never run this casually; it deletes named volumes and database data
# docker compose down -v
```

## Production checklist

- Domain A record points to the VPS
- Firewall allows 22, 80, and 443 only
- Port 5432 is not public
- Port 8000 is not public
- Fresh JWT keys were generated
- `.env` permissions are `600`
- CORS contains the exact frontend domain
- Alembic has one head and upgrades successfully
- `/health` returns HTTP 200
- HTTPS works
- Backups run and have been test-restored
- Original database and JWT secrets exposed in earlier logs/ZIP files are rotated

## 15. Foundation services added

The Compose stack also runs a `maintenance` service. It periodically:

- expires old marketplace requests and pending offers;
- expires ended subscriptions;
- marks unpaid installments overdue;
- updates overdue-loan flags;
- marks zero-balance loans completed.

```bash
docker compose logs -f maintenance
```

Create the first platform administrator after the migrations are complete:

```bash
docker compose exec api python scripts/create_superadmin.py \
  --phone 58000000 \
  --email owner@example.com \
  --first-name Platform \
  --last-name Owner
```

Keep `WEB_CONCURRENCY=1` while WebSocket delivery uses the included in-memory channel manager. Use Redis pub/sub before scaling FastAPI horizontally or increasing worker count.

LoanHub is deployed as a cash-only release. Electronic provider adapters are not loaded. Every cash-in and cash-out operation must be recorded by an authorized cashier or finance role, reconciled to a receipt, and included in branch cash controls.
