# Wacom STU raw-stroke assembly — Phase 7

Following the successful STU-540 local SDK diagnostic (353 reports), LoanHub
now has an internal Go stroke-assembly foundation.

The assembler receives validated STU numeric reports and groups pen-down
contacts into separate strokes. It retains raw x/y, pressure, device time and
sequence values in **temporary process memory only**, with limits of 10,000
points, 300 strokes and 120 seconds. It rejects repeated sequence numbers,
backwards timestamps and use after the capture is sealed, and permits
best-effort explicit in-memory discard.

This is **not connected to the Wacom diagnostic CLI**, localhost HTTP
routes, LoanHub backend, or browser. It deliberately does not serialize,
upload, persist, log or sign with these raw strokes.

Security and integration requirements before live signing:
- Native SDK session lifecycle/verified device provenance, not a browser
  declaration of `wacom_stu`.
- Documented SDK calibration and device coordinate/pressure ranges.
- Explicit borrower identity verification, per-contract consent, and
  company/branch-scoped authorized signing sessions.
- Backend envelope validation, encrypted evidence storage, PDF rendering,
  audit trail, key management and crash-safe transaction reconciliation.
- Signed, replay-protected short-lived connector communication and secure
  display of a preview in the browser.

The legacy email-OTP signing path remains untouched.
