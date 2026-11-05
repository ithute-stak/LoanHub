# Wacom browser preview — field lifecycle safeguards

The reusable `WacomSignatureField` and `useWacomSignatureSocket` now
prevent late asynchronous responses from crossing contract/field sessions:

- Every authorization request captures a local generation. Field/session
  changes, disabling, cancellation, and unmount invalidate that generation.
- A late backend approval is ignored and cannot open a WebSocket for a
  different displayed signature field. Explicit operator cancellation
  invalidates outstanding approvals even if the network response arrives later.
- Only one pending authorization request is allowed per field at a time.
- The WebSocket hook requires at least one fully validated stroke frame
  before treating a `complete` control event as a successful test preview.
- The preview stays browser-memory-only and cannot sign a PDF or upload
  handwriting evidence. Cancellation clears displayed ink.

## Verification still needed

These lifecycle guards must be exercised through browser integration tests
with intentionally delayed backend approval, rapid contract switching,
operator cancellation, and physical Wacom disconnection/revocation. The
WebSocket server remains unmounted and no production capture is enabled.
