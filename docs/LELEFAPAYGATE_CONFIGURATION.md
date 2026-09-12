# LelefaPayGate configuration

LoanHub treats LelefaPayGate as platform infrastructure owned by the Super Admin.

## Source of truth

Operational LelefaPayGate configuration is stored in the `lelefapaygate_configurations` PostgreSQL table. The API key and webhook signing secret are encrypted with purpose-bound AES-GCM before persistence. LoanHub derives the encryption key from `FERNET_SECRET_KEY`, which remains a deployment-level master secret and must not be exposed to the frontend.

The following values are managed from **Super Admin → Platform configuration → LelefaPayGate**:

- enabled / disabled state
- gateway API base URL
- merchant API key
- webhook signing secret
- outbound request signing
- request timeout
- webhook timestamp tolerance
- default collection provider
- default payout provider

LelefaPayGate operational credentials must not be placed in `.env`. Legacy `LELEFAPAYGATE_*` environment values are ignored by the runtime database synchronization layer.

## Security behavior

- Only the `SUPERADMIN` role can read or update the control-plane configuration endpoints.
- The API key and webhook signing secret are never returned in plaintext after they are saved.
- Audit records contain configuration state and change names, never secret values.
- Enabling the integration requires both an encrypted API key and encrypted webhook signing secret.
- Corrupt or undecryptable credentials fail closed and leave LelefaPayGate unavailable.
- Signed webhook processing can retain the stored webhook secret even when new gateway transactions are disabled, allowing in-flight transactions to be reconciled safely.

## Deployment

Apply the database migration before opening the Super Admin configuration screen:

```bash
cd apps/backend
alembic upgrade head
```

After migration, open `/superadmin/lelefapaygate`, save the test or live merchant credentials, then enable the integration. New requests load the database configuration automatically; editing `.env` or restarting LoanHub is not required for configuration changes.
