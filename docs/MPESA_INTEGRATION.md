# LoanHub Vodacom M-Pesa OpenAPI integration

## Scope

LoanHub integrates M-Pesa in the FastAPI backend. Browser and mobile clients never receive the company API key, RSA public key, generated session ID, service-provider secret, or callback controls.

The Lesotho defaults are:

- Market: `vodacomLES`
- Country: `LES`
- Currency: `LSL`
- Host: `https://openapi.m-pesa.com`

The company enables only products approved for its Vodacom organisation and developer application.

## Supported M-Pesa products

| Product | LoanHub use |
|---|---|
| Generate SessionKey | Server-to-server authentication, cached securely per company/environment |
| C2B Single Stage | Normal one-time borrower repayments |
| C2B Multi Stage | Repayment flows requiring additional customer/merchant confirmation |
| B2C Single Stage | Loan disbursement and approved customer refunds |
| B2B Single Stage | Approved company-to-business payments |
| Reversal | Controlled reversal of an eligible completed M-Pesa transaction |
| Query Transaction Status | Callback fallback and automatic reconciliation |
| Update Transaction Status | Controlled update for multi-stage provider workflows |
| Direct Debit Create | Create a borrower-authorised repayment mandate |
| Direct Debit Payment | Collect an instalment under an active mandate |
| Query Beneficiary Name | Confirm the recipient before B2C disbursement |
| Query Direct Debit | Confirm mandate activation/status |
| Cancel Direct Debit | Stop future mandate collections |

## Runtime architecture

See `diagrams/architecture.svg` and `diagrams/architecture.png`.

1. Next.js calls LoanHub FastAPI.
2. FastAPI resolves the user, company, branch and role.
3. LoanHub creates a local payment and provider-attempt record before calling M-Pesa.
4. The company session manager generates and caches a SessionKey.
5. M-Pesa returns synchronously or sends a result to the public callback listener.
6. Duplicate callbacks are ignored using a deterministic payload hash.
7. Missing callbacks and timeouts are reconciled by Query Transaction Status.
8. A confirmed payment updates the loan, accounting, receipt and notifications.

## Important transaction rule

An HTTP success or `INS-0` can indicate that a request was accepted for processing. LoanHub finalises money movement only when the returned provider status or final callback/status query confirms completion. A provider timeout remains `processing`; it is never immediately retried as a new payment because that could charge the customer twice.

## Main routes

### Shared and borrower routes

- `GET /api/v1/mpesa/products`
- `GET /api/v1/mpesa/transactions`
- `GET /api/v1/mpesa/transactions/{payment_id}`
- `POST /api/v1/mpesa/payments/{payment_id}/refresh-status`
- `GET /api/v1/mpesa/payments/{payment_id}/receipt`
- `POST /api/v1/mpesa/direct-debits`
- `GET /api/v1/mpesa/direct-debits`
- `POST /api/v1/mpesa/direct-debits/{mandate_id}/query`
- `POST /api/v1/mpesa/direct-debits/{mandate_id}/cancel`

### Company routes

- `GET/PUT /api/v1/mpesa/configuration`
- `POST /api/v1/mpesa/configuration/test`
- `POST /api/v1/mpesa/beneficiary-name`
- `POST /api/v1/mpesa/b2b`
- `GET /api/v1/mpesa/reversals`
- `POST /api/v1/mpesa/payments/{payment_id}/reversal-request`
- `POST /api/v1/mpesa/reversals/{reversal_id}/approve`
- `POST /api/v1/mpesa/direct-debits/{mandate_id}/collect`
- `POST /api/v1/mpesa/provider-transactions/{provider_transaction_id}/update-status`

### Platform routes

- `GET /api/v1/mpesa/platform/overview`
- `GET /api/v1/mpesa/platform/configurations`

### Provider callback

- `POST /api/v1/mpesa/callbacks/transaction-result`

## User interfaces

- Borrower: `/borrower/mpesa`
- Company: `/company/mpesa`
- Platform owner: `/superadmin/mpesa`
- Borrower queries: `/borrower/queries`
- Company queries: `/company/queries`
- Platform query management: `/superadmin/queries`

The floating Query, Chat and Assistant buttons are held in one vertical dock. On small screens the assistant opens above the entire dock, so it does not cover the Query or Chat controls.

## External verification requirement

The exact field names for each enabled product must be checked against the current Vodacom Lesotho documentation attached to the company application. The Query Transaction Status contract was supplied directly. Other payloads follow the OpenAPI conventions used by the portal but must be confirmed during sandbox certification, especially response URL, multi-stage status fields, direct-debit fields, B2B party codes and reversal references.
