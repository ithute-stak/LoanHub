# LoanHub PC Bridge — first-party company-managed workstation architecture

## Product decision (8 November 2026)

No Tailscale or external identity-provider dependency. Workstations use **LoanHub authentication** and device possession proofs. Authentication and authorisation are separate. Public IP changes must never determine the signed-in operator's identity or break existing authenticated workstations.

### Access flow

1. On startup, the Go PC bridge connects **outbound** by HTTPS to a tightly scoped LoanHub bridge API. Its local browser UI binds to 127.0.0.1 only, includes CSRF controls, and never exposes a remote listener.
2. Each person signs in **personally** with LoanHub credentials. Backend checks active status, any required password change, tenant membership, company and branch, and determines roles server-side. A borrower/client or unauthorized staff member is denied without access to borrower details.
3. Company owner/admin registers the PC's locally generated Ed25519 public key, and an independent authorized administrator approves enrollment. Administrator then manages which employees, within the company/branch, can use this PC. A **single approved workstation may have many employee assignments**; an employee may use several individually approved PCs.
4. Operators select their own account and authenticate with their **own** credentials every session. The owner may select an employee to provision or manage, but may **not impersonate that employee or sign on their behalf**.
5. Login exchange and later sensitive operations require fresh backend-verifiable Ed25519 device proof with short-lived, one-use nonce bound to workstation, company, operator, requested purpose, and expiry. No trust is based on public IP, MAC address or a browser-supplied role.
6. Authenticated, assigned lending operators can create and offer loans within their separate LoanHub permissions; borrower lookup and Wacom signature capture are constrained to matching company/branch and specific loan/contract.
7. Operators may **enroll** their own signature via the physical tablet and independent review. A captured image is stored encrypted with provenance. A verified capture is **not** a standing signing authorization. Each document signing requires explicit authorization from that operator for that **specific finalized document version**, followed by server-side verification, immutable audit and artifact integrity checks. Borrowers separately consent to and sign their own contract. Signing on behalf of another operator is forbidden.

### Data model to introduce in a later migration

- `wacom_workstations`: company_id, workstation_id, public_key, status, approval/revocation, branch scope, operator-independent workstation identity.
- `wacom_workstation_operators`: company_id, workstation_id, employee_user_id, allowed branch, role permissions, status, granted_by, granted_at, revoked_by, revoked_at; unique(company_id, workstation_id, employee_user_id).
- `wacom_bridge_sessions`: unique session id, operator_user_id, workstation id, tenant/branch id, issued/expires/last_verified times, revocation information, device-proof binding; no reusable passwords stored.
- `wacom_document_signing_intents`: operator id, loan/contract id, finalized document digest, signing reason, short expiry, explicit operator authorization, usage count one, evidence and audit links.

### Authorization invariant

All relevant protected backend endpoints must require a validated **LoanHub operator token AND active assignment AND current workstation proof**. The first-party network gateway must permit *only* required routes to reach login and device-proof checks, with rate-limiting, TLS, monitoring, and revocation; it must not simply open the existing staging API to arbitrary internet clients. Never use an IP allowlist as the only client gate.

### Existing code and migration notes

- Current `wacom_workstation_enrollments` ties a device to `operator_user_id`. Preserve existing rows/approved evidence and migrate to a separate device-to-operator assignment model; do not silently alter that table or contract signing.
- Existing Wacom workstation challenge endpoints are **preview-only**, and local evidence review explicitly returns `usable_for_signing: false`. Keep these fail-closed semantics until the document-scoped signing workflow exists.
- Owner/admin configuration and employee operation must be different sessions. Independent evidence reviewers cannot review their own captures.

### Delivery gates

A. Introduce multi-operator assignment schema and API, role/branch authorization, audited owner/admin provisioning and revocation.
B. Add role-aware Go login and operator switcher, active assignment check and logout; preserve existing capture flow.
C. Extend device proof binding from preview-only to narrowly authorized bridge operations, allow dynamic public IP behind a hardened gateway with protection against brute-force login.
D. Test same PC with two employees, denied debtor, revoked employee, wrong company/branch, wrong device key, network change, operator switching, signature capture, and review.
E. Add separate document-version-specific signing and consent workflow **only after** a focused legal, security and audit review. Do not activate automatic image pasting or implicit signatures.

The new `wacom_bridge_access_policy.py` and tests define the entry policy only. They are not wired into live routes and do not change current access behavior.
