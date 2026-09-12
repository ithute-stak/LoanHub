# LoanHub Docker deployment

The repository layout is:

```text
apps/
  backend/
  frontend/
compose.yaml
```

## Recommended deployment: separate application containers

This starts PostgreSQL, Redis, the Alembic migration job, FastAPI, the maintenance worker, and Next.js.

```bash
chmod +x scripts/*.sh apps/backend/docker/entrypoint.sh docker/start-all-in-one.sh
./scripts/docker-init.sh
```

Review `.env`. For another machine or production domain, replace all three values:

```dotenv
PUBLIC_APP_URL=https://loan.example.com
CORS_ORIGINS=https://loan.example.com
NEXT_PUBLIC_API_URL=https://api.loan.example.com/api/v1
```

`NEXT_PUBLIC_API_URL` is embedded during the Next.js image build, so rebuild the frontend after changing it.

Start LoanHub:

```bash
./scripts/docker-up.sh
```

Open:

```text
Frontend: http://localhost:3000
FastAPI:  http://localhost:8000
API docs: http://localhost:8000/docs
```

Useful commands:

```bash
docker compose ps
./scripts/docker-logs.sh
docker compose exec backend alembic current
docker compose exec backend python -m pytest
docker compose restart backend frontend
./scripts/docker-backup.sh
./scripts/docker-down.sh
```

Do not run `docker compose down -v` unless you intentionally want to delete PostgreSQL, Redis and stored LoanHub files.

## Optional: one application container, two ports

FastAPI, the maintenance worker and Next.js can share one application container while PostgreSQL and Redis stay separate:

```bash
docker compose -f compose.single-container.yaml up -d --build
```

Ports remain:

```text
3000 → Next.js
8000 → FastAPI
```

The separate-container configuration is recommended because frontend and backend can be restarted and scaled independently.

## Persistent data

Docker named volumes preserve:

- PostgreSQL database data
- Redis append-only data
- Uploaded files, generated reports, receipts and branch-submission PDFs

## Troubleshooting

### Frontend cannot reach the API

The browser uses `NEXT_PUBLIC_API_URL`. `http://localhost:8000` works only when the browser and Docker host are the same computer. For LAN or public deployment, use the Docker host IP or API domain and rebuild.

### Backend waits for PostgreSQL

```bash
docker compose logs db migrate backend
```

### Migration failed

```bash
docker compose run --rm migrate alembic current
docker compose run --rm migrate alembic upgrade head
```

### Reset only application images

```bash
docker compose down
docker compose build --no-cache backend frontend
docker compose up -d
```
