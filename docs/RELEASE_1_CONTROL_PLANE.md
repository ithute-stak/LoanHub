# LoanHub Release 1 control plane

This release adds enforceable security, financial and data-governance controls. It does not bypass LelefaPayGate or mark an external refund complete without a trusted gateway confirmation.

## Security

- TOTP authenticator MFA with encrypted secrets, replay prevention and ten one-time recovery codes.
- Account lockout after configurable failed sign-in attempts.
- Constant-time dummy password verification for unknown accounts.
- Refresh-session metadata, individual revocation, global session-version revocation and immediate access-token invalidation by session ID.
- Role impersonation is disabled by default and must be deliberately enabled.

## Audit integrity

- Existing audit rows are hash chained during migration.
- New audit rows are sealed automatically in transaction order.
- Sealed records cannot be updated or deleted through SQLAlchemy sessions.
- Platform verification checks the complete chain. Tenant verification recomputes the integrity of every company-visible event without disclosing other tenants' events.

## Payments and integrations

- Refunds, reversals and chargebacks use a dedicated adjustment ledger.
- Refund/reversal requests require full-payment allocation consistency and independent maker/checker approval.
- Cash reversals update the loan schedule and accounting reversal together.
- Electronic adjustments remain `processing` until LelefaPayGate provides a trusted confirmation; LoanHub has no manual “mark gateway refund paid” endpoint.
- Outbound company webhooks use an encrypted signing secret, HMAC signatures, idempotent outbox records, exponential retry, attempt history, dead-letter status and controlled replay.
- Production webhooks require HTTPS and public network destinations. Existing endpoints must rotate their secret once before delivery.

## Accounting and reconciliation

- Accounting periods can be opened, locked and closed.
- Once a company configures periods, entries outside an open period are rejected.
- Draft manual journals require an independent poster and cannot be posted into locked/closed periods.
- Bank statement lines are fingerprinted against duplicate import and matched once to succeeded payments with equal amounts.

## Customer and credit controls

- Dedicated guarantor and collateral records replace generic operating-record placeholders.
- Guarantor consent is required before verification.
- Borrowers can raise tracked complaints and exercise access, correction, portability, restriction, objection and deletion rights.
- Company data-protection staff can only see requests for borrowers related to their company; platform administrators retain system-wide oversight.

## Deployment sequence

1. Back up PostgreSQL and confirm restore readiness.
2. Deploy the backend and run `alembic upgrade head` to revision `i9y3a5b7d809`.
3. Deploy the frontend.
4. Confirm `/health`, `/health/ready` and the Control & Assurance centre.
5. Rotate every pre-existing outbound webhook signing secret.
6. Configure test LelefaPayGate credentials and exercise signed callbacks before enabling live credentials.

Live refunds, card acquiring, PayPal, bank rails, M-Pesa and EcoCash remain subject to provider contracts, approved credentials and any applicable regulatory certification.
