# LoanHub + IthutePayBridge Integration & Operations Handbook

**Audience:** product owners, finance operations, developers, security reviewers and deployment engineers.

**Purpose:** this is the cross-system handover for LoanHub and IthutePayBridge (IPB). It records the boundary between lending operations and payment-provider orchestration so a payment, payout, mandate or reversal is never treated as final from a browser, a mobile notification or an unverified callback.

## 1. Production truth and scope

LoanHub is the system of record for tenant membership, borrower and loan relationships, lending decisions, repayment posting, internal accounting, audit, chat and user-facing state. IthutePayBridge is the payment-orchestration system: it owns merchant applications, provider adapters, provider operation tracking, its payment lifecycle, reconciliation, settlement tooling, gateway webhooks and its own double-entry gateway accounting.

A provider such as M-Pesa is the external settlement network. Its acceptance response is not automatically a settled payment. Both platforms must preserve asynchronous states and reconcile them.

LoanHub currently has its own provider-oriented payment configuration and LelefaPayGate integration boundary. IPB is a separate gateway integration path. Before production, select one active settlement path for each business operation and make that choice explicit in configuration and monitoring. A single repayment or payout must never be submitted through both paths.

This handbook documents the intended server-to-server IPB path. It does not claim that a live merchant account, M-Pesa credentials, provider certification, webhooks or settlement agreement has been configured.

## 2. System responsibilities

| Concern | LoanHub | IthutePayBridge | External provider |
|---|---|---|---|
| Tenant, borrower, loan and repayment rules | Authoritative | Receives references only | None |
| Money instruction | Decides whether a repayment/payout is allowed | Validates merchant request and drives provider operation | Accepts/rejects/processes |
| Financial state shown to LoanHub users | LoanHub transaction + loan/accounting records | Provides signed lifecycle status | Source for actual network result |
| Provider credentials and session keys | Must not enter mobile/browser | Stores/uses provider credentials server-side | Issues credentials |
| Webhook receipt | Verifies IPB signature and posts idempotently | Verifies provider callback and emits durable merchant webhook | Sends provider callback |
| Reconciliation | Reconciles LoanHub loan/accounting records with gateway IDs | Reconciles gateway state with provider operations | Transaction-status source |
| Realtime user notice | WebSocket/FCM after verified LoanHub update | Optional gateway dashboard realtime | No authority |

## 3. End-to-end topology

    LoanHub web / Flutter app
              |
              | authenticated HTTPS
              v
    LoanHub FastAPI and PostgreSQL
              |
              | server-to-server API key, idempotency key
              v
    IthutePayBridge API and PostgreSQL
              |
              | provider credentials and provider API
              v
    M-Pesa or another approved provider

    Provider callback -> IthutePayBridge verification/reconciliation
                      -> signed merchant webhook -> LoanHub verification/posting
                      -> LoanHub WebSocket + FCM user update

Apps never receive an IPB API key, provider API key, private signing secret or provider session key. PostgreSQL is durable state in both systems; Redis, WebSocket and FCM are delivery/coordination mechanisms only.

## 4. Environments and credentials

Create separate IPB merchant applications for sandbox/UAT and production. The corresponding keys use distinct test and live identities. Do not reuse a production secret in a simulator or developer environment.

Each LoanHub deployment needs:

- the IPB HTTPS base URL;
- a non-production or production IPB merchant API key;
- an IPB webhook signing secret;
- optional IPB request-signing configuration;
- a configured callback URL reachable over HTTPS;
- durable storage for the LoanHub-to-IPB resource ID, LoanHub reference and idempotency key.

Store these only in the LoanHub backend deployment secret store. Do not put them in Flutter Dart defines, Android resources, Next.js public variables, source files, screenshots, tickets or Git commits. Rotate any secret that has been exposed.

## 5. Required identity and correlation mapping

Every instruction must carry stable LoanHub references as IPB metadata. LoanHub must persist the returned IPB resource ID before it waits for a callback.

| LoanHub value | IPB use |
|---|---|
| LoanHub payment/transaction ID | Primary internal correlation |
| Loan ID | Metadata for repayment/disbursement posting |
| Borrower ID | Metadata; never a substitute for recipient verification |
| Company and branch ID | Tenant/branch reconciliation scope |
| Actor user ID | Audit correlation |
| Loan reference or customer reference | Provider-visible reference where appropriate |
| LoanHub operation UUID | Idempotency key basis |
| IPB payment/payout/mandate ID | Persisted external resource identifier |
| IPB event ID | Webhook de-duplication key |

Use an idempotency key that represents the intended business operation, such as loan-410-repayment-1. On timeout or a 5xx response, retry only with that same key after checking the current IPB resource/status. Never generate another financial instruction merely because the client did not receive a response.

## 6. Core flows

### 6.1 Borrower repayment / collection

1. LoanHub validates tenant, borrower, loan state, amount and repayment permissions.
2. LoanHub creates a local pending payment/instruction with a durable idempotency key.
3. LoanHub backend creates an IPB payment intent with the borrower phone, amount, LSL currency, LoanHub reference and metadata.
4. IPB drives the provider collection and records provider operations.
5. LoanHub does not mark an instalment paid when the intent is merely created, requires confirmation, processing or unknown.
6. On a signed payment.succeeded IPB webhook, LoanHub verifies signature/replay/idempotency and posts the repayment exactly once.
7. LoanHub updates its account/loan records, creates the user-facing receipt/state and emits a realtime event.

### 6.2 Loan disbursement / B2C payout

1. LoanHub completes its own approval, contract, affordability and maker-checker requirements.
2. LoanHub creates a durable pending disbursement instruction and an IPB payout.
3. IPB submits and reconciles the provider payout.
4. LoanHub marks the loan disbursed only when payout.succeeded is verified or a status query confirms final success.
5. A failed, cancelled or unknown payout is not a disbursed loan. The original history remains; reversal and correction use compensating records.

### 6.3 Direct debit

1. LoanHub records the borrower agreement and its mandate terms.
2. LoanHub requests an IPB mandate and stores the returned mandate ID.
3. Before each charge, LoanHub/IPB checks mandate state according to the enabled provider workflow.
4. Each charge is an idempotent operation with a distinct LoanHub reference.
5. Cancellation stops future charges but never erases previous mandate or charge history.

### 6.4 Reversal

A reversal is a new controlled action against an eligible confirmed transaction. IPB creates the provider reversal and its compensating gateway journal. LoanHub creates its own compensating lending/accounting effect only after the final reversal status is verified. No historical payment or loan record is deleted to simulate a reversal.

## 7. Status model and posting rule

Treat these as non-final: created, requires_confirmation, awaiting_customer, processing and unknown. Treat failed, expired and cancelled as final failures. Treat succeeded as a final success only after it comes from a verified IPB webhook or an authenticated status refresh. Treat reversed or partially_reversed as post-settlement corrections that require controlled LoanHub accounting action.

The LoanHub UI may show the latest reported status, but a notification or an HTTP 200 response is not itself a settlement decision. LoanHub Money must reserve the loud money-received experience for a provider-confirmed/verified success.

## 8. Request authentication and webhook verification

IPB merchant calls use a Bearer merchant key and financial creates use Idempotency-Key. IPB can additionally require timestamp, nonce and HMAC request signing. When enabled, construct the exact canonical request described in the IPB Consumer Integration Guide, including method, path and SHA-256 of the raw body.

For IPB-to-LoanHub webhooks:

1. read the raw request bytes before decoding JSON;
2. parse the timestamp and v1 digest from X-IPB-Signature;
3. reject a stale timestamp using the agreed tolerance;
4. compute HMAC-SHA256 over timestamp + "." + raw-body with the merchant webhook secret;
5. compare using a constant-time comparison;
6. store X-IPB-Event-ID before posting business effects;
7. return a quick 2xx for duplicates that have already been safely processed;
8. perform slow follow-up work asynchronously, but make the initial ledger transition transactional.

Never rely on a browser redirect, FCM message, frontend callback or provider-looking payload that bypasses IPB’s signature verification.

## 9. Failure, retry and reconciliation rules

| Scenario | Required action |
|---|---|
| LoanHub request timeout | Retry only with same idempotency key; fetch IPB status |
| Duplicate IPB webhook | Detect event ID/resource state; no duplicate repayment/disbursement |
| Provider accepts then later completes | Keep processing; wait for verified webhook/status refresh |
| IPB unavailable | Preserve LoanHub pending instruction; do not silently create a direct provider transaction |
| Callback signature fails | Reject, audit safely, alert operations; do not post money |
| Amount/reference mismatch | Quarantine for finance review; do not automatically apply to a loan |
| Provider/IPB final state differs from LoanHub | Reconcile by stored resource IDs and investigate with audit trail |
| Reversal needed | Create controlled compensating reversal; never delete history |

Daily operations should reconcile IPB payment/payout/transfer state, provider references, LoanHub payment state, LoanHub loan allocation and accounting journals. Investigate every unresolved processing/unknown item and every monetary mismatch before declaring a reporting period closed.

## 10. Security, privacy and audit

- Enforce LoanHub company and branch scope before any instruction is created or posted.
- Use HTTPS for every API/webhook endpoint and restrict provider callback ingress where IP ranges are available.
- Keep least-privilege IPB merchant applications separate from platform administrator accounts.
- Do not log API keys, HMAC secrets, PINs, full account details or raw sensitive provider payloads.
- Audit configuration changes, financial approval, status refreshes, webhook receipt, posting, reversal and reconciliation decisions.
- Encrypt stored secrets and managed files. Retain records according to approved legal, financial and privacy policies.
- Rotate API/webhook secrets, provider credentials and deployment access on staff departure or suspected exposure.
- Use test data only in sandbox/reviewer environments.

## 11. LoanHub mobile and realtime boundary

Flutter calls LoanHub, never IPB. LoanHub’s foreground WebSocket and FCM background notifications are for timely user experience. Authoritative state is reloaded from LoanHub API after resume/reconnect.

A money-created event means that an instruction exists; it must not say money received. Only LoanHub’s verified final-payment path may produce a success/received event. The same rule applies to chat, calls and notifications: delivery is not a database authority.

For business telephony, see LoanHub Call Management and the Vodacom telephony request. Telephony recording/call metadata must stay on the controlled SIP/PBX path; it is separate from IPB payment processing.

## 12. Deployment and go-live checklist

- [ ] LoanHub and IPB are deployed on HTTPS with internal PostgreSQL/Redis access only.
- [ ] IPB sandbox merchant application, key and webhook endpoint are configured.
- [ ] LoanHub backend secret store has sandbox key/secret; mobile/web clients have none.
- [ ] Create, success, failure and unknown simulator paths are tested.
- [ ] Same-key retry and duplicate webhook delivery are tested.
- [ ] LoanHub persists IPB IDs, references and event IDs.
- [ ] Repayment posting, payout posting, reversal and reconciliation are reviewed by finance.
- [ ] Production merchant/provider onboarding and callback registration are approved.
- [ ] Production test is performed with a controlled low-value transaction.
- [ ] Monitoring, alert routing, backup restore and incident contacts are confirmed.
- [ ] Only then are live credentials enabled.

## 13. Operational ownership

LoanHub operations own borrower/loan correctness, company access, repayment allocation, disbursement approval, LoanHub accounting and customer communication. IPB operations own merchant application configuration, provider routing, gateway settlement/reconciliation, webhook delivery and platform-level payment incidents. The provider owns external network availability and its settlement confirmation.

Escalate an incident with the LoanHub request ID, LoanHub transaction ID, IPB resource ID, IPB event ID, provider reference, timestamps, masked customer number, tenant/company and current status. Never paste secrets or full customer financial data into an incident ticket.

## 14. Related repository documentation

LoanHub:
- docs/MPESA_INTEGRATION.md
- docs/LELEFAPAYGATE_CONFIGURATION.md
- docs/CALL_MANAGEMENT_INTEGRATION.md
- docs/mobile/REALTIME_ARCHITECTURE.md
- docs/MPESA_SECURITY_AND_GO_LIVE.md

IthutePayBridge:
- docs/CONSUMER_INTEGRATION_GUIDE.md
- docs/LOANHUB_INTEGRATION.md
- docs/API_REFERENCE.md
- docs/SECURITY.md
- docs/SANDBOX_TESTING_GUIDE.md
- docs/ADMIN_PRODUCTION_DEPLOYMENT.md
