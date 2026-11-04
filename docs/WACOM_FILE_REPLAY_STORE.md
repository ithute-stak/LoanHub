# Wacom preview — durable local replay protection

This adds a file-backed implementation of the Go
`previewTicketReplayStore` interface for one enrolled workstation.

Properties:
- Atomic `O_CREATE|O_EXCL` creation prevents concurrent reuse of a
  cryptographically hashed ticket JTI.
- Used JTIs survive restart of the Go connector.
- Records use mode 0600 within a preprovisioned real directory that must
  have mode 0700 and be owned by the connector OS user.
- The connector does not silently create a replay directory in /tmp,
  follow a symlink as its leaf directory, or log JTI values.
- File and directory `fsync` are required before success; I/O failure
  fails closed. Partial writes remain used, rather than granting reuse.
- Tests exercise restart persistence, concurrent single-use consumption,
  symlink/permission rejection and unsafe directory paths.

This is **single-workstation**, local-filesystem replay protection, not
a fleet-wide multi-host replay database. Do not share tickets between
workstations. The authorized workstation UUID in the ticket must be
verified against enrolled workstation identity.

Deployment prerequisites:
1. Provision a trusted local private directory on a persistent filesystem.
2. Protect its parent directories from untrusted modification; use host
   filesystem ownership and backup policy. Do not use ephemeral/tmpfs
   storage.
3. Set strong key-management, workstation enrollment and transport
   authentication and implement backend session revocation.
4. Never delete used-ticket records before ticket expiry plus acceptable
   clock drift. The current implementation intentionally does not
   automatically prune records; implement vetted expiration-aware pruning
   before high-volume deployment.
5. Wire an authenticated endpoint only after revocation, rate limiting,
   local device provenance, and session lifecycle are implemented.

**There is still no HTTP route, installed key, captured-point stream or
legal signing permission.** Existing email OTP signing remains unchanged.
