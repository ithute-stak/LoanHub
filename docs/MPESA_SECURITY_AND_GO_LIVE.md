# M-Pesa security and go-live checklist

## Secrets

- Never expose M-Pesa credentials to Next.js client components, Flutter, logs, GitHub or support chat.
- Company API keys and RSA public keys are encrypted using AES-GCM before database storage.
- Use separate high-entropy `SECRET_KEY` and `FERNET_SECRET_KEY` values.
- Keep JWT keys outside the repository.
- Rotate any key or session string that has been pasted into chat, a ticket or a screenshot.

## Network

- Use HTTPS for LoanHub and callbacks.
- Register the actual production origin/static IP as a trusted source in the M-Pesa application.
- Do not use `*`, `127.0.0.1` or `localhost` for production trusted sources.
- Restrict callback access at the reverse proxy or firewall according to Vodacom's current guidance.
- `X-Mpesa-Callback-Token` is an optional LoanHub defence. Do not assume M-Pesa sends custom headers unless the product supports them; enforce IP/network controls where required.

## Financial controls

- Borrowers can initiate only their own repayments and mandates.
- Finance roles initiate beneficiary queries, B2B payments, direct-debit collections and reversal requests.
- Company management approves reversals and controls production configuration.
- Branch staff cannot access another branch's loan-linked payments.
- B2B requires company-wide finance access.
- Provider attempts, callbacks, status queries and user actions remain auditable.

## Go-live process

1. Register or confirm the company's M-Pesa business/organisation account.
2. Link the developer account to the organisation.
3. Create a versioned M-Pesa application.
4. Enable only contractually approved products.
5. Configure usage time, per-transaction, daily and customer limits.
6. Register trusted source IPs/origins and callback URL.
7. Complete sandbox scenarios, including failure and timeout cases.
8. Hand the application to the linked organisation for review.
9. Complete Vodacom end-to-end testing/certification.
10. Enter production credentials into LoanHub and enable production only after approval.
11. Monitor first transactions and reconcile them independently.

## Production safeguards

- `PAYMENT_MOCK_MODE=false`
- `ENVIRONMENT=production`
- HTTPS callback base URL
- Redis available for session cache and realtime
- Maintenance worker running
- Database backups tested
- M-Pesa configuration connection test successful
- Query Transaction Status enabled
- No development credentials or sample shortcodes present
- Company-specific settlement and accounting reviewed
