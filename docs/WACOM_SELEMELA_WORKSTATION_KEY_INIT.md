# Wacom — Selemela local workstation Ed25519 identity setup

**This feature prepares local credentials only. It does not register or
approve a device automatically, and does not start live pen streaming.**

On the Ubuntu workstation with the STU-540 attached:

```bash
cd ~/LoanHub-Wacom/services/wacom-connector
go test ./...
go build -o loanhub-wacom-connector .
umask 077
mkdir -p "$HOME/.local/share/loanhub-wacom"
chmod 700 "$HOME/.local/share/loanhub-wacom"
./loanhub-wacom-connector --init-workstation="$HOME/.local/share/loanhub-wacom"
```

Run `--init-workstation` **only once** after the implementation has been
merged and pulled. The tool refuses to overwrite an existing identity.
It writes `workstation-identity.json` with mode 0600 to an existing
owned, non-symlink private directory (0700). Treat it as a private key:
never paste, upload, commit, email, log or move its contents. Backup
and recovery policies must be agreed before using live enrolled devices.

The tool prints **only**:
```json
{
  "workstation_id": "generated-workstation-uuid",
  "ed25519_public_key_base64": "generated-public-key"
}
```

The JSON can be entered in the tenant-authenticated
`POST /api/v1/contract-signing/workstations` request by an authorized
lending operator. A **different** company owner/admin must approve the
pending enrollment before backend challenge issuance will succeed.

Security constraints:
- Never create the identity as root or inside a Git checkout or Docker image.
- Never use an untrusted/shared/mounted directory or sync the private seed
  into cloud storage without an approved encrypted key-management policy.
- On Linux, protect the private key with workstation disk encryption.
- The current seed is a mode-0600 software key; hardware-backed key
  protection, security review and rotation remain a future hardening step.
- A different administrator should confirm the public key fingerprint
  over an authenticated enrollment channel to mitigate key substitution.
- Key initialization does not itself authenticate to LoanHub: the
  challenge-response client, TLS-backed transport, session and revocation
  checks, preview-ticket issuance and browser stroke transport remain to do.

Do not activate real customer contract signing as a result of this setup.
