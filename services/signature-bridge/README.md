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

## Optional staging-only background sync

The user service starts after reboot (when linger is enabled), but does not
send anything until explicitly configured. No token or password is saved by
the Signature Bridge. Provision a separate authenticated **short-lived**
token helper on the workstation; it must be an absolute executable path
owned by the current desktop user with mode `0700` (no group/other access).
The helper prints only the fresh API access token to standard output, and
must not echo credentials to logs. It must be reviewed by the operator.

Create `~/.config/loanhub-signature-bridge/sync.env` as a private 0600 file:

```ini
LOANHUB_SIGNATURE_BRIDGE_AUTO_SYNC_ENABLED=true
LOANHUB_SIGNATURE_BRIDGE_MODE=staging
LOANHUB_SIGNATURE_BRIDGE_SYNC_URL=https://VERIFIED-STAGING-HOST/api/v1/signature-bridge/imports
LOANHUB_SIGNATURE_BRIDGE_TOKEN_PROVIDER=/home/USER/path/to/reviewed-token-provider
```

Restart the user service with `systemctl --user restart loanhub-signature-bridge.service`.
The service checks pending records at approximately 60-second intervals.
It refuses production mode and retains unsent records after failures.
**Do not enable this with live customer data:** true device capture, signer
verification, audit approval, key rotation, and production policies remain
unfinished.

## Not yet implemented
- Physical Wacom STU-540 capture bridge, signer verification UI, operator authentication, consent UI.
- Production token provisioning, identity-verification UI and conflict resolution UI. Unattended staging sync is opt-in and requires an administrator-provided short-lived token helper; no helper is bundled.
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
