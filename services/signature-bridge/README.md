# LoanHub Signature Bridge — offline-first starter

This is a **staging-only foundation**, not yet a completed desktop application or a signing system.

## Implemented
- Private SQLite queue; Fernet-encrypted capture payload at rest; vault key in a mode-0600 local file.
- HMAC-hashed phone aliases, including slash-separated Lesotho numbers.
- Tenant-scoped lookups for clients and stable user-ID lookups for officers.
- Explicit conflict on multiple signature records (even for one signer).
- Background Python vault process and Linux systemd user service that can auto-start after reboot.
- Tests for normalization, tenant isolation and matching conflicts.

## Remote synchronization (staging only)

The backend Docker image includes a gated import route at `POST /api/v1/signature-bridge/imports` and an Alembic migration. It accepts identity-claimed captures only into encrypted **quarantine**, not an approved signature registry. It is disabled unless `ENVIRONMENT=staging` and `LOANHUB_SIGNATURE_BRIDGE_IMPORT_ENABLED=true` with a separate Fernet key in `LOANHUB_SIGNATURE_BRIDGE_VAULT_KEY`. Use an isolated staging HTTPS endpoint and a short-lived authenticated operator token; do not use production credentials.

On the local workstation, a *supervised* run is supported:

```sh
LOANHUB_SIGNATURE_BRIDGE_ACCESS_TOKEN='short-lived-staging-token' \\
  .venv/bin/python bridge.py sync --url https://YOUR-VERIFIED-STAGING-HOST/api/v1/signature-bridge/imports
```

This command sends at most 25 queued records over verified HTTPS, never saves a token, retains failed records, and only marks entries acknowledged after a 202 quarantine confirmation. It does **not** apply signatures to contracts.

## Not yet implemented
- Physical Wacom STU-540 capture bridge, signer verification UI, operator authentication, consent UI.
- Unattended sync scheduler, token provisioning and renewal, conflict resolution UI. A supervised HTTPS sync command exists, but requires an authenticated staging operator and a deployed remote API.
- Contract-specific signing approval and approved import into LoanHub forms.
- Windows installer and production key management / encryption hardening.

The local CLI only accepts data from a **trusted, consent-aware integration**. Do not import actual customer signatures until verified identity, proper authorization, key backup and secure sync are implemented.

## Linux development quick start

```sh
cd services/signature-bridge
python3 -m venv .venv
. .venv/bin/activate
pip install cryptography
python3 -m unittest discover -s tests -v
python3 bridge.py status
```

Install autostart after arranging a suitable Python environment with `cryptography` available to the systemd unit:

```sh
bash install-linux.sh
systemctl --user is-enabled loanhub-signature-bridge.service
systemctl --user is-active loanhub-signature-bridge.service
sudo loginctl enable-linger "$USER"  # optional: launch at boot before login
```

Never run the vault as root. Keep local `vault.key` backed up securely: without it, encrypted records cannot be decrypted. Revoking a signer must prevent further use or sync.
