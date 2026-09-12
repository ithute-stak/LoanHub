# Architecture

## Runtime components

```text
Browser / PWA
    |
    | HTTPS, access token, refresh cookie, X-Company-ID
    v
Caddy reverse proxy
    |
    v
FastAPI API  ---- WebSocket channels (single API worker foundation)
    |
    +---- PostgreSQL
    |
    +---- M-Pesa / EcoCash adapter boundary
    |
    +---- maintenance worker
```

The backend is a modular monolith. This keeps financial transactions and tenant authorization within one database transaction while leaving clear service boundaries for later extraction.

## Core domains

- **Identity**: users, people, refresh tokens and company memberships.
- **Tenant administration**: companies, branches, staff and role assignment.
- **Borrower profile**: employment, affordability and consent.
- **Marketplace**: loan requests, redacted cards, paid unlocks and offers.
- **Loan servicing**: accepted loans, schedules, disbursement, repayments and allocations.
- **Billing**: plans, subscriptions, resource limits and platform payments.
- **Operations**: maintenance reconciliation, audit fields and WebSocket events.

## Frontend state strategy

- Redux owns authentication and stable entity collections such as companies, staff and branches.
- `TenantProvider` owns the selected company membership and persists the company ID.
- `AppDataProvider` loads role-specific platform, company or borrower data and exposes analytics/actions to pages.
- Axios attaches both the bearer token and `X-Company-ID` and serializes refresh-token attempts with a refresh mutex.

## Scaling notes

The included WebSocket manager is process-local. `WEB_CONCURRENCY=1` is therefore the safe default. Before multiple API workers or multiple VPS instances, replace it with Redis pub/sub or another shared message broker. Background maintenance can later move to Celery/RQ/Arq when Redis and distributed scheduling are introduced.
