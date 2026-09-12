# LoanHub Validation Runbook

## 1. Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
./scripts/generate_secrets.sh
# Edit .env for PostgreSQL, Redis, domains, and integrations.
alembic upgrade head
pytest -q
python scripts/validate_release.py
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Useful smoke checks:

```bash
curl http://localhost:8000/
curl http://localhost:8000/openapi.json
curl http://localhost:8000/health
```

## 2. Frontend

```bash
cd frontend
corepack enable
pnpm install --frozen-lockfile
pnpm typecheck
pnpm build
pnpm dev
```

For local same-origin API proxying, create `.env.local`:

```env
API_PROXY_TARGET=http://localhost:8000
AUTH_COOKIE_GUARD=true
```

Open `http://localhost:3000` and verify at minimum:

1. Login and refresh after a page reload.
2. Open two tabs and select different company roles; each tab must retain its own role.
3. Add a new staff person with a password.
4. Add another role using the same phone without a password; only one user account must exist.
5. Switch between roles and verify navigation and backend permissions.
6. Switch between companies and verify no stale records remain from the previous company.
7. Test staff, borrowers, loans, payments, accounting, treasury, files, notifications, and chat.
8. Test widths around 320, 375, 768, 1024, and 1440 pixels.
9. Confirm wide tables scroll horizontally on phones rather than widening the page.
10. Run production mode with `pnpm build && pnpm start`.

## 3. Docker Compose

```bash
cd backend
./scripts/generate_secrets.sh
docker compose up --build
```

The frontend Docker build now executes both `pnpm typecheck` and `pnpm build`. The backend scheduler is protected against duplicate execution across the default two Uvicorn workers.
