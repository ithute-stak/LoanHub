# PC-to-LoanHub full flow regression test (synthetic only)

## What it verifies

`loanhub_pc_full_flow_test.go` drives the actual localhost operator UI
against a temporary TLS `httptest` LoanHub API, using fictional identifiers
and a generated PNG. It verifies:

1. A user submits a phone number/password and selects an active company.
2. The existing LoanHub HTTPS login returns a bearer token.
3. The authenticated status API identifies the operator.
4. The client lookup returns a borrower ID and name within the selected company.
5. Mismatched signer name or absent consent prevents Wacom capture.
6. A single injected test capture generates a local review image in memory.
7. An upload is impossible before a separate review confirmation.
8. The upload includes the borrower ID, consent reference, PNG and SHA-256.
9. LoanHub accepts it as `pending_review` only, never as document signing.
10. The preview and borrower lookup are removed from the local session after
    receipt; expired captures and logout are handled safely.

Run on the local workstation (or CI) without any STU hardware or LoanHub VPS:

```bash
cd services/wacom-connector
go test -run 'TestPCToLoanHubSyntheticCaptureUploadAndReviewReceipt|TestPCExpiredCaptureNeverUploads' -v
go test ./...
```

**This is a protocol contract test, not a real LoanHub database test.**
The fake API imitates LoanHub responses and does not verify real credential
authentication, PostgreSQL row-level tenant security, encryption or malware
scanning. The actual physical STU-540 read-to-PNG test passed separately on
the local PC, producing 231 reports, 132 contact points and four strokes.

## Remaining test gate

After this PR and its backend dependencies pass review, deploy the **existing**
LoanHub backend to an isolated test environment, not a new Wacom bridge.
Verify with fictional accounts and borrowers:

- Login with the real LoanHub authentication endpoint
- Real tenant-scoped borrower lookup and audit controls
- Real encrypted signature upload and safe duplicate handling
- Independent evidence verification with two different authorized users
- Signature review image retrieval, permissions and revocation checks
- Contract-specific evidence and authorization-status read APIs

Keep real client/operator handwriting and production signing disabled until
those controls and the legal consent process have been validated.
