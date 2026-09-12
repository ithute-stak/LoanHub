# LoanHub Frontend

Responsive Next.js 16 frontend for the LoanHub multi-tenant loan marketplace and loan-management platform.

## Portals

- `/superadmin` — platform owner oversight, companies, branches, loans, plans and payments.
- `/company` — tenant dashboard, marketplace, loans, payments, products, branches, staff, subscription and settings.
- `/borrower` — borrower dashboard, requests, offers, accepted loans, repayments and profile.

## State architecture

- Redux Toolkit: authentication, companies, company staff and branches.
- `TenantProvider`: selected company membership and `X-Company-ID` context.
- `AppDataProvider`: role-specific data, analytics and domain actions.
- Axios interceptors: access-token attachment, refresh mutex and tenant header.

## Development

```bash
cp .env.example .env.local
pnpm install
pnpm typecheck
pnpm lint
pnpm dev
```

Use this local environment value when FastAPI is running locally:

```dotenv
NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
```

## Production build

```bash
pnpm typecheck
pnpm lint
pnpm build
pnpm start
```

The backend must allow the exact frontend origin through `CORS_ORIGINS`. For refresh cookies, deploy the frontend and API on HTTPS, preferably under the same registrable domain such as `app.example.com` and `api.example.com`.
