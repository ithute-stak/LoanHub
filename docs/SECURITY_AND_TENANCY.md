# Security and Tenant Isolation

## Tenant selection

Company users may belong to more than one company. Every tenant API request resolves membership from the database. When more than one active membership exists, the frontend sends:

```http
X-Company-ID: <selected-company-uuid>
```

The header is never trusted by itself. The backend verifies that the authenticated user has an active membership for that company.

## Data isolation rules

- Platform administrators may inspect all tenants.
- Borrowers may read only their own profile, requests, offers, loans and payments.
- Company users may access only records whose `company_id` matches the resolved membership.
- Company owners and administrators have company-wide visibility.
- Non-management staff with a branch assignment are restricted to that branch for loans, offers and loan-linked payments.
- Lenders receive redacted borrower marketplace cards until a subscription entitlement or successful paid unlock exists.
- The backend, not the frontend, enforces every role and scope check.

## Authentication

- Short-lived RS256 access tokens.
- Refresh tokens are stored server-side by JTI and delivered through an HTTP-only cookie.
- Logout revokes the refresh token and is idempotent for stale cookies.
- Passwords are hashed with bcrypt through Passlib.
- JWT keys are mounted as files and copied into protected runtime storage before the API drops privileges.

## Financial controls

- Payment requests use unique idempotency keys.
- Provider callbacks require a callback secret in this foundation.
- Accepted-offer selection locks both request and offer rows.
- One company may submit only one offer per request.
- One accepted loan may exist per request and per offer.
- Marketplace identity access is recorded by company, request, payment and user.

## Required production enhancements

Before handling real customer money or regulated identity documents:

- add provider-native callback-signature verification;
- store KYC documents in encrypted object storage with malware scanning;
- introduce audit-log immutability and retention policies;
- configure rate limiting at Caddy/API gateway level;
- use a managed secrets vault;
- add MFA for platform and company owners;
- conduct penetration testing and authorization regression testing;
- confirm Lesotho lending, data-protection, AML/KYC and payment regulations with qualified professionals.
