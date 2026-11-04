# Wacom workstation proof of possession — development contract

This phase implements matching Go and Python primitives for a future
authenticated Wacom workstation enrollment protocol. It **does not**
register an HTTP route or enable capturing signatures.

Proposed flow:
1. An authenticated backend operator starts an eligible contract
   preview session.
2. The backend retrieves the enrolled workstation's **stored** Ed25519
   public key, checks its company/branch/owner and current revocation.
3. The backend creates and durably stores a random 32-byte challenge,
   scoped to exact workstation UUID and session UUID, expiring within
   30 seconds.
4. The workstation signs the exact UTF-8 canonical challenge bytes
   with its locally protected Ed25519 private key; only its signature
   leaves the workstation.
5. Backend verifies the enrolled public key, scope, expiry and signature,
   then atomically consumes the saved challenge ID in a persistent
   transaction. Expired/used/revoked challenges fail closed.
6. The backend **separately** checks current pad-session eligibility and
   ticket issuance authorization before granting temporary preview
   permission. Legal signature capture remains disabled.

Canonical signed message:
```text
LOANHUB-WACOM-WORKSTATION-POP-V1
<workstation-uuid>
<pad-session-uuid>
<base64url-32-byte-nonce>
<expiry-unix-seconds>
```
The final message contains a trailing newline. The example placeholders
are descriptive only, not real credentials or identifiers.

The Go helper does not load private keys itself. The Python helper
accepts the independently loaded public key and a required atomic
consume callback. Neither helper accepts a browser-provided trusted
workstation identity.

**Still required**: database enrollment and challenge tables with
tenant and branch authorization; secure private-key provisioning and
rotation; backend challenge creation/verification routes; authenticated
network transport and backend revocation checks; a verified temporary
stroke stream; test-only browser rendering; finally separate borrower
identity verification, consent, protected evidence storage, and PDF signing.
