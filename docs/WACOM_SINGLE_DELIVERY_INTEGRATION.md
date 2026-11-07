# LoanHub Wacom — Single-Delivery Integration Code

## Scope and status

This branch consolidates the **application-level Wacom handwriting evidence capture and independent review workflow** into one coding milestone. It stacks on the prior draft PR work (through #605). No code on this branch has been deployed or approved for production, and no real workstation/API acceptance test has been performed as part of this delivery.

**Very important:** Verified handwriting evidence is not a reusable legal signature and cannot sign a contract. Borrower-controlled, contract-version-specific authorization and final signed-document issuance remain separate, disabled functionality.

## Implemented code path

1. The employee runs the Go connector on their **local Ubuntu PC** with the installed official STU-540 SDK samples. Nothing Wacom-specific runs on the LoanHub VPS.
2. At `http://127.0.0.1:8767/`, the employee authenticates through LoanHub's existing HTTPS `/api/v1/auth/login` API, selecting an active company membership. The Go client also denies inactive accounts and password-change-required accounts. Tokens remain in PC memory.
3. The employee checks their signature status or searches for a company-scoped borrower by exact National ID, explicitly confirms the displayed name, records a consent reference, and initiates hardware capture.
4. The official PC SDK produces pen reports. The Go process checks calibration, generates an in-memory bounded PNG, shows the preview, and requires a second explicit approval before upload. It clears PNG bytes on discard, upload completion and session expiry.
5. The PC uploads the PNG and digest directly to `/api/v1/local-signatures/captures` with the selected company and bearer token. The LoanHub backend validates PNG/size/hash/tenant, requires a conclusive clean ClamAV scan, encrypts the stored object, writes company/branch-confidential pending evidence and a same-transaction submission audit.
6. A **different company-management employee** opens the same PC UI, loads the pending review queue, opens the authenticated private PNG preview, and records verification or rejection with evidence reference, reason and explicit identity/consent review. The backend prevents self-review and enforces tenant isolation again.
7. A reviewed capture stays **non-signing and non-reusable**. Neither upload nor review modifies saved borrower signatures, finalizes a PDF, or authorizes any contract.

## Separate code components

- `services/wacom-connector/loanhub_pc_review.go`: company-scoped review queue, authenticated PNG preview, two-person decisions, guarded responses.
- `services/wacom-connector/loanhub_pc_ui.go`: browser operator and reviewer panels, session-bound review images and CSRF-protected decisions.
- `services/wacom-connector/loanhub_pc_client.go`: active-user/active-company login check.
- `services/wacom-connector/loanhub_pc_capture_flow.go`: best-effort RAM zeroization of disposable images.
- `apps/backend/routers/local_signatures.py`: capture upload audit as part of the evidence transaction.
- `apps/backend/services/file_service.py`: early rejection before storage for an indeterminate Wacom scan, plus object cleanup if database flush fails.
- `services/wacom-connector/loanhub_pc_review_test.go`: synthetic offline review contract tests, **authored but not executed in this delivery**.

## Commands for a future approved test (DO NOT run until ready)

On a dedicated isolated LoanHub staging environment (after independent isolation and secrets review), integrate the stacked PRs, then run the real-API synthetic smoke harness described in `docs/WACOM_REAL_LOANHUB_API_SMOKE.md`.

On the PC (not the VPS), with the approved *staging* HTTPS hostname and exact SDK executables:

```bash
cd services/wacom-connector
go test ./...
go build -o loanhub-wacom-connector .
./loanhub-wacom-connector --pc-ui \
  --loanhub-origin=https://APPROVED-STAGING-API-ONLY \
  --enable-local-capture \
  --sdk-query="$HOME/wacom-stu-sdk/sdk-extracted/Linux/x86_64/query" \
  --sdk-pen-sample="$HOME/wacom-stu-sdk/sdk-extracted/Linux/x86_64/simpleInterface"
```

Open `http://127.0.0.1:8767/` on that same PC. Never port-forward this local UI, share JWTs, enter real borrower identities into staging, or expose the STU-540 to the VPS. The first end-to-end test should use only meaningless test scribbles and synthetic accounts.

## Deferred checks (by instruction: testing later)

- Run the Go tests, backend focused pytest suites and complete GitHub Actions CI.
- Manually review stacked PR integration/merge conflicts and confirm the exact image deployed to **isolated staging**.
- Validate actual STU-540 pen-to-browser preview, PNG upload, scan rejection, encryption/decryption and two-person approval.
- Validate cross-company denial, self-approval denial, expired session, device unplug, scanner outage, partial transaction failure and synthetic cleanup.
- Verify operations policy for retention, review audits, access logging, incident response, backups and disaster recovery.
- Separately design and obtain approval for true document-specific signing with explicit signer consent, the exact immutable PDF hash/version, revocation semantics and atomic finalization.

## Release boundary

Do not merge, deploy to production, enable a real customer workflow, or claim legally binding PDF signatures from this branch without the later testing and authorization. Successful compilation alone will not prove physical PC-to-API integration.
## Final coding-only hardening (after consolidation)

The code-only pass also adds:

- Fail-closed Go checks for foreign/inactive operator capture eligibility, unexpected signature permissions, inconsistent borrower-lookup responses and malformed identity results.
- A private reviewer browser integration test covering company context, authorization headers, CSRF denial, decision submission, queue invalidation and logout.
- Additional negative-path operator and borrower API tests using in-process synthetic HTTPS responses only.
- Immediate RAM cleanup for expired capture previews (including when an expired preview URL is requested).
- An opt-in offline verification entrypoint at `scripts/wacom_verify_code_only.sh`. It prints usage by default; tests run only with `--execute-offline-tests`.

### Deliberately deferred execution

The final code-only pass was committed **without manually invoking the test script, CI, a GitHub merge, database migration or deployment**. GitHub Actions may run automatically on branch pushes under the repository's existing workflow triggers; an automatic run is not authorization to deploy. After all coding is frozen, inspect the latest head SHA, review the actual GitHub Actions result, run the opt-in local test script and execute approved isolated staging acceptance.

### Stop conditions for later acceptance

Stop immediately if an API reply enables signing/reuse, the reviewer belongs to another company or is the capturing operator, ClamAV is unavailable, encryption is off, the physical PC cannot show genuine STU-540 strokes, the backend routes differ from the release candidate, or the staging deployment touches production resources. Do not accept a green CI result as proof of a physical signing workflow.
