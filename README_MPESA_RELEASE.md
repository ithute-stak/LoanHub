# LoanHub v1.2 - Vodacom M-Pesa OpenAPI web integration

This release adds the M-Pesa web integration for borrowers, lending companies and the platform owner. Flutter integration is intentionally deferred until the web/API workflow is validated in the Vodacom sandbox.

## Main user functions

### Borrower

- C2B single-stage and multi-stage loan repayments.
- Own M-Pesa transaction history and status refresh.
- PDF repayment receipt after confirmed provider completion.
- Direct-debit mandate creation, status query and cancellation.
- Query Centre for payment, support, feature, technical and training requests.
- One floating Query/Chat/Assistant dock with no overlapping controls.

### Lending company

- Per-company encrypted M-Pesa configuration and SessionKey connection test.
- Query Beneficiary Name, enforced by the backend before M-Pesa B2C loan disbursement.
- B2B company payments for authorised company-wide finance roles.
- Direct-debit collection from active, confirmed mandates.
- Transaction status refresh and C2B multi-stage status update.
- Reversal request and company-management approval workflow.
- Purpose-specific PDF confirmations and accounting/loan finalisation.
- Company Query Centre for requirements and support requests to the platform owner.

### Platform owner

- M-Pesa configuration and transaction overview across companies without decrypted credentials.
- Processing, completed, failed, reversed, direct-debit and callback metrics.
- Query Centre for reviewing, responding to and updating borrower/company submissions.
- Unmatched/failed callback visibility for operational support.

## Installation

1. Back up PostgreSQL.
2. Copy the backend into the local `apps/loan_backend` folder and the frontend into `apps/frontend`, or apply the patch archive.
3. Copy `backend/.env.example` to `.env` and restore your own secure values. Do not copy credentials from a previous archive blindly.
4. Apply the migration:

```bash
cd apps/loan_backend
source .venv/bin/activate
alembic upgrade head
alembic current
```

Expected head:

```text
b8d5e21f9a30
```

5. Ensure the API and maintenance worker are both running.
6. Start the frontend and open Company > M-Pesa.
7. Configure Sandbox first, test the SessionKey, then execute the testing manual.

## Required runtime settings

```env
PAYMENT_MOCK_MODE=false
MPESA_HOST=https://openapi.m-pesa.com
MPESA_HTTP_TIMEOUT_SECONDS=45
MPESA_CALLBACK_TOKEN=<private-random-value>
REDIS_URL=redis://localhost:6379/0
```

Company API keys, public keys, service-provider codes and enabled products are entered in the Company M-Pesa settings page and stored encrypted.

## Security model

- M-Pesa secrets never enter Next.js client code.
- Company credentials are encrypted with AES-GCM.
- The API key is encrypted with M-Pesa's RSA public key to request a SessionKey.
- Session values are cached per company/environment in Redis or bounded in-process cache.
- Phone/key/secret-like values are masked or redacted in stored operational payloads.
- Duplicate callbacks are detected by payload hash.
- Provider attempts are persisted before the network call, allowing safe status reconciliation after timeout.
- A timeout remains processing; LoanHub queries the original transaction rather than creating a second charge.

## External provider verification

The current Query Transaction Status contract is based on the supplied Vodacom M-Pesa portal documentation. Field names for the other products follow the OpenAPI portal conventions and must be compared with the current Vodacom Lesotho documentation attached to the actual application during sandbox certification. Production use also requires organisation linking, enabled products, registered trusted sources/callbacks, review, end-to-end testing and go-live approval.

## Documents

- `docs/MPESA_INTEGRATION.md`
- `docs/MPESA_SECURITY_AND_GO_LIVE.md`
- `docs/MPESA_TESTING_CHECKLIST.md`
- `LoanHub_Mpesa_Testing_Manual.docx`
- `LoanHub_Mpesa_Testing_Manual.pdf`
