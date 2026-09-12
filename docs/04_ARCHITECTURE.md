# Technical Architecture

LoanHub is implemented as a modular monolith. This keeps tenant authorisation and financial workflows inside one PostgreSQL transaction while preserving clear routers, schemas, services and model boundaries.

## Runtime topology

See `assets/diagrams/01-system-context.png`.

- Caddy terminates TLS and routes `/api/*` and WebSocket traffic to FastAPI while serving the Next.js frontend.
- PostgreSQL stores business data, audit events, notifications, accounting and report metadata.
- Redis distributes realtime events across API workers.
- The maintenance worker performs recurring reconciliation and midnight reports.
- Managed files and generated reports are stored in an encrypted persistent media volume.

## Source tree

```text
LoanHub/
├── apps/
│   ├── backend/       FastAPI, models, services, routers, migrations
│   └── frontend/      Next.js pages, providers, Redux, API clients, UI
├── brand/             Product and developer branding
├── docs/              Engineering and operational documentation
├── infra/caddy/       Reverse-proxy configuration
├── scripts/           Validation and deployment automation
├── secrets/           Runtime key location; no secrets committed
├── compose.yaml       Complete service stack
└── .github/workflows/ CI/CD validation and Hostinger deployment
```

## Architectural principles

- Server-side tenant and branch enforcement; the browser is never the authority.
- One shared realtime connection per browser tab.
- Idempotent payment, report and accounting operations where retries are expected.
- Safe ordinary-user errors and detailed restricted platform-owner incidents.
- Database migrations are reviewed history, not disposable generated files.
