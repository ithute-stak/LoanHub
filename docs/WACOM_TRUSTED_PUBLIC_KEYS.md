# Wacom connector — locally pinned Ed25519 backend verification keys

The Go workstation connector has a pure trust-file loader. This file is
**not** populated by HTTP, browser input, Wacom SDK output or unverified
ticket claims.

Provisioning prerequisites:
1. The backend administrator generates an Ed25519 **private** signing key
   in the backend secret manager and publishes only its **public** key
   through a separately authenticated provisioning process.
2. An enrolled Ubuntu workstation administrator provisions a
   persistent, privately owned directory (mode 0700), with secure parent
   directories, and a regular trust file (mode 0600) owned by the connector
   OS account. Do not use a symlink or a world-readable path.
3. The file contains a strictly bounded versioned JSON bundle:

```json
{
  "version": 1,
  "keys": [
    {
      "id": "trusted-backend-key-1",
      "public_key_base64": "<BASE64_OF_32_PUBLIC_KEY_BYTES>"
    }
  ]
}
```

The placeholder must be replaced with the independently verified
32-byte Ed25519 public key. Never store the backend private signing key
on the workstation. Deploy keys with authenticated rotation, expiration
and revocation; pin key identity as part of enrollment.

The loader rejects missing/unsafe directory permissions, symlink files,
non-regular files, wrong ownership, overlarge files, duplicate IDs,
unknown JSON fields, bad key formats and malformed trusted key sets.

**Not yet connected:** Loading keys at connector startup, device
enrollment and revocation, an authenticated local endpoint, backend
ticket issuance routes, secure streaming, and legal contract signing.
CI tests validate the loader in isolation, not physical pad capture.

Do not deploy this file as a ready-to-use application configuration
until the complete workstation provisioning lifecycle is in place.
Existing email-OTP signing remains unchanged.
