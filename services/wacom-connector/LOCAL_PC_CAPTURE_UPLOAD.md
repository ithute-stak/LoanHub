# Phase 5: Local STU-540 signature capture and pending-review upload

**Runs only on the employee's Linux PC, not the LoanHub VPS.**

This feature is currently a **draft implementation** for a controlled test
environment. Do not use real signatures or live customer information before
physical STU-540 testing, backend approval workflow and security review.

## Launch in non-capture mode

```bash
cd services/wacom-connector
go test ./...
go build -o loanhub-wacom-connector .
./loanhub-wacom-connector --pc-ui \
  --loanhub-origin=https://YOUR-VERIFIED-LOANHUB-TEST-API
```

The operator login and client lookup UI is available at
`http://127.0.0.1:8767/`. The capture control is hidden when no
SDK paths are explicitly configured.

## Explicitly enable local capture (test environment only)

This option requires Wacom's installed official SDK tools on the **PC**:

```bash
./loanhub-wacom-connector --pc-ui \
  --loanhub-origin=https://YOUR-VERIFIED-LOANHUB-TEST-API \
  --enable-local-capture \
  --sdk-query="$HOME/wacom-stu-sdk/sdk-extracted/Linux/x86_64/query" \
  --sdk-pen-sample="$HOME/wacom-stu-sdk/sdk-extracted/Linux/x86_64/simpleInterface"
```

Do not expose either local loopback port through a public reverse proxy,
SSH forwarding, or network router.

## Workflow

1. Staff member logs in with existing LoanHub credentials and an active
   company. LoanHub's API returns the operator signature status.
2. For a borrower, find the exact National ID and verify the displayed name
   and borrower ID against the person who is physically present.
3. Choose the signer (operator/client), type their full name, enter a consent
   evidence reference and check explicit consent.
4. Click **Capture handwriting**. The configured local Wacom SDK sample
   reads stylus strokes; the Go process creates a limited-size PNG in memory.
   The SDK binary path is controlled by startup flags, never a web request.
5. Review the captured handwriting on the local screen. **Discard** or
   separately confirm approval to upload.
6. The PC HTTPS client uploads the image and digest directly to LoanHub with
   the logged-in operator's access token and selected company.
7. LoanHub returns `pending_review`. It cannot be used for signing or
   automatically copied into any contract.

The application holds preview data in RAM for up to two minutes, then
requires a new capture. Logout or a new client lookup discards the pending
preview. No pen images are written to the PC filesystem by this workflow.

## Important remaining validation

- Verify the official SDK sample runs correctly when started from the local
  browser UI. The current diagnostic method uses a pseudo-terminal and may
  need a native SDK worker in unattended desktop sessions.
- Confirm that LoanHub signature storage encryption and malware scanning
  are working in the controlled environment.
- Add verified identity/consent audit evidence and approval API before
  any signature is activated.
- Add separate per-document signing authorization and revocation enforcement.
- Test account logout, expired sessions, device disconnection, interrupted
  capture, repeated uploads, and multiple operators on one workstation.

No staging or production Docker infrastructure change is required.
