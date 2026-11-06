# Local Wacom PC ↔ LoanHub API client (phase 2)

This module runs **on the operator's computer**. It adds an HTTPS client to
the existing Go Wacom connector; it does not add a VPS proxy, Wacom server,
document signer or pen-capture endpoint.

The flow is:

1. Call `NewLoanHubPCClient("https://api.loanhub.co.ls", nil)` (use the
   configured, verified LoanHub API origin; no URL paths).
2. The PC application calls `Login(ctx, phone, password, otp, companyID)`
   using the existing LoanHub account. `companyID` must be an active membership.
   Store the access token **in memory only**, never logs or config files.
3. Call `OperatorSignatureStatus(ctx)`. If `requires_capture=true`,
   prompt for an operator signature; `pending_review` means do not recapture
   or treat it as an approved signing credential.
4. Call `FindClient(ctx, nationalID)` to retrieve a tenant- and branch-scoped
   borrower ID and full name. Confirm the identity with the person physically
   present, independently of a text search match.
5. After explicit consent, capture a PNG using a reviewed, local *official*
   Wacom STU SDK adapter. Call `UploadPNG(ctx, "client", borrowerID,
   consentReference, pngBytes)`. For the operator signature use
   `UploadPNG(ctx, "operator", "", consentReference, pngBytes)`.
6. The API responds `pending_review`. **No saved signature is automatically
   usable for a loan document or contract.** Review, activation, and individual
   signing consent are separate LoanHub workflows not implemented here.
7. Call `Logout()` when the application session ends.

The backend is being reviewed in draft PR #586. Do **not** point the client
at production until the backend passes CI, security review, and a controlled
deployment. The Go integration tests use synthetic identities and
`httptest.NewTLSServer`; they do not need the physical Wacom pad.

The current default local HTTP service at `127.0.0.1:8765` remains
**diagnostics-only**. This client deliberately provides no unauthenticated
browser signing route. We still need a reviewed PC login UI and a real
official-SDK pen-to-PNG adapter before the complete workflow is usable.
