# API Workflows

All paths below are under `/api/v1`.

## Company onboarding

1. `POST /company-registration/` creates the owner, person, company and owner membership atomically.
2. The company remains `pending` and cannot enter tenant operations.
3. Platform owner uses `PATCH /companies/{id}/approve`, `/reject`, `/suspend`, `/activate` or `/deactivate`.
4. The owner selects a plan through `POST /billing/subscriptions/checkout`.
5. Owners configure `/branches`, `/company-staff/accounts` and `/loan-products` within plan limits.

## Borrower marketplace

1. `POST /borrower-registration/` creates the borrower account and profile.
2. Borrower grants profile-sharing consent in `/borrowers/me`.
3. `POST /loan_requests/` creates and broadcasts a request.
4. Lenders list redacted cards through `GET /marketplace/requests`.
5. A subscription may include full marketplace access; otherwise the company calls `POST /marketplace/requests/{id}/unlock`.
6. After successful access, `GET /marketplace/requests/{id}` includes the borrower detail.
7. The company submits `POST /loan-offers/`.
8. Borrower lists offers through `GET /loan-offers/request/{request_id}`.
9. Borrower accepts exactly one with `POST /loan_requests/{request_id}/offers/{offer_id}/accept`.

## Disbursement and repayment

1. Acceptance creates the loan and repayment schedule.
2. Authorized finance staff call `POST /loans/{loan_id}/disburse`.
3. Borrower calls `POST /loans/{loan_id}/repay`.
4. Successful callbacks update the payment, loan balance and installment allocations.
5. `GET /payments/` and `GET /loans/` are automatically scoped to platform, tenant/branch or borrower.

## Payment callbacks

```http
POST /api/v1/payments/callbacks/mpesa
X-Callback-Secret: <configured-secret>
Content-Type: application/json
```

The production adapter must additionally validate the exact cryptographic signature required by the selected provider.
