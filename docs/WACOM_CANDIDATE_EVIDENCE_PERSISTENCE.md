# Candidate Wacom capture persistence — internal only

The internal pad_capture_persistence service links the existing:
- loan_contracts row (locked; company and borrower checked)
- contract_pad_signing_sessions row (locked; operator and exact hash checked)
- contract_pad_capture_evidence row (one row per session)
- encrypted object storage (AES-256-GCM with bound associated data)

No HTTP endpoint invokes this service. The caller must authenticate the
local workstation and establish a verified identity/consent event before
setting capture_provenance_verified. NEVER map this boolean from a request
body or rely on a browser-provided capture_source string.

On success the session becomes captured, not completed, and the loan contract
remains unsigned. On database error the service attempts to delete the
ciphertext object; interrupted writes/crashes require periodic orphan-object
reconciliation, and object-storage/db atomicity cannot be guaranteed.

Still required before enabling live signing:
1. Wacom-supported native pen capture adapter (no vendor binary in repo).
2. Mutual workstation-to-backend authentication, authenticated session token
   and nonce/replay protection.
3. Borrower identity, explicit consent + opt-in-to-save flow.
4. Per-company authorization and branch checks at HTTP boundary.
5. Signed PDF generation and durable audit/event ledger.
6. Evidence lifecycle/retention/revocation and reconciliation.
7. Cryptographic key provisioning, rotation, backup and recovery.

Only deploy this code after CI and security review; no production signing
routes are enabled by this change.
