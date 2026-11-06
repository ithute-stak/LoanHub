# LoanHub Signature Bridge — offline-first starter

This is a **staging-only foundation**, not yet a completed desktop application or a signing system.

## Implemented
- Private SQLite queue; Fernet-encrypted capture payload at rest; vault key in a mode-0600 local file.
- HMAC-hashed phone aliases, including slash-separated Lesotho numbers.
- Tenant-scoped lookups for clients and stable user-ID lookups for officers.
- Explicit conflict on multiple signature records (even for one signer).
- Background Python vault process and Linux systemd user service that can auto-start after reboot.
- Tests for normalization, tenant isolation and matching conflicts.

## Local pen-stroke capture interface (staging foundation)

The local `capture-strokes` command now accepts a **bounded JSON envelope on
standard input** and immediately encrypts it inside the workstation vault.
This is an interface for a separately reviewed native Wacom STU SDK adapter,
**not yet a working STU-540 capture driver**. The CLI flags below attest that
the operator verified identity and obtained consent; they are not independent
cryptographic evidence and must not be treated as such.

Test envelope (synthetic points only):

```json
{"format":"loanhub-pen-strokes-v1","strokes":[[{"x":0.1,"y":0.2,"pressure":0.5,"t":1},{"x":0.2,"y":0.3,"pressure":0.7,"t":2}]]}
```

The native adapter must emit normalized x/y coordinates and pressure in
`[0,1]`, strictly increasing per-stroke timestamps in milliseconds, with
at least two points per stroke. Unexpected fields and excessive data are
rejected. Capture is a separate operator-triggered action; the background
service never grabs pen data on its own and port 8765 is untouched.

Do not use with real signatures until device ownership, staff/client
verification, consent records and revocation flows are finished.

## Optional native Wacom capture adapter (no SDK binary bundled)

The local bridge supports an operator-initiated `capture-wacom` command.
The workstation administrator must separately install a reviewed executable
that wraps the vendor STU SDK, and exposes:

```sh
/path/to/reviewed-wacom-adapter --capture-strokes-json
```

The executable must return one `loanhub-pen-strokes-v1` JSON envelope on
stdout and exit successfully. Coordinates and pressure are normalized to
`[0,1]`, timestamps strictly increase within each stroke, and all capture
data must fit within 128 KB. Raw pen data must not appear in stderr logs.

A typical explicitly consented **staging-only** invocation is:

```sh
.venv/bin/python bridge.py capture-wacom \
  --sdk-adapter /home/USER/path/to/reviewed-wacom-adapter \
  --company-id VERIFIED-STAGING-COMPANY-UUID \
  --signer-kind client \
  --verified-signer-id VERIFIED-STAGING-BORROWER-UUID \
  --phones '58123456 / 63123456' \
  --consent-reference STAGING-CONSENT-REFERENCE \
  --identity-verified --consent-confirmed
```

The CLI flags record operator assertions, **not proof of signer identity or
legally sufficient consent**. This must not be used for live customer records
until a verified capture UI, device ownership, and audit workflow exist.
The executable is never called by the auto-start background service and
does not open a network listener, so the existing Wacom diagnostic service
at `127.0.0.1:8765` is preserved. No external Wacom SDK binaries are checked
into LoanHub.

## Read-only workstation preflight before pen capture

After building the Go connector on Selemela and configuring the private
`wacom-sdk.json`, check prerequisites **without recording a signature**:

```sh
cd services/wacom-connector
LOANHUB_SIGNATURE_BRIDGE_MODE=staging \
  ./loanhub-wacom-connector --bridge-capture-preflight
```

Run from the signing workstation's interactive terminal. A successful
preflight confirms file ownership/modes, available SDK sample executables,
an installed util-linux `script` program, and the staging-only setting.
It prints `prerequisites_ready` with `hardware_verified: false`;
**it does not open the tablet, exercise any pen strokes, or verify consent**.
A successful preflight is not evidence of a physically working STU-540.

Only after the preflight and an independently verified staging operator
session should the operator test `capture-wacom` with a disposable
signature. Never use real customer handwriting as test data.

## Staging-only official STU sample adapter on Selemela

The Go Wacom connector now includes an **opt-in local CLI**
`--capture-strokes-json`, implemented using the existing Go SDK pen parser
and vendor sample launcher. The official STU SDK binaries are **not included**.

On the **test workstation only**, use a current Go build from this feature
branch and configure the two verified official Wacom sample paths privately:

```sh
cd services/wacom-connector
go test ./...
go build -o loanhub-wacom-connector .
mkdir -p "$HOME/.config/loanhub-signature-bridge"
chmod 700 "$HOME/.config/loanhub-signature-bridge"
# Edit this file with your locally verified Wacom SDK paths:
# ~/.config/loanhub-signature-bridge/wacom-sdk.json
chmod 600 "$HOME/.config/loanhub-signature-bridge/wacom-sdk.json"
```

The private JSON configuration must contain:

```json
{
  "sdk_query": "/home/USER/wacom-stu-sdk/sdk-extracted/Linux/x86_64/query",
  "sdk_pen_sample": "/home/USER/wacom-stu-sdk/sdk-extracted/Linux/x86_64/simpleInterface"
}
```

Replace both paths with the executables that were actually verified on the
workstation. The Go adapter must be run in an interactive terminal with
`LOANHUB_SIGNATURE_BRIDGE_MODE=staging` and only disposable test strokes.
Its stdout contains sensitive pen coordinates, and should be consumed
directly by the encrypted Python bridge, **never logged or pasted into chat**.

To run the integrated local staging test after preparing the SDK config,
set the desktop user’s mode to staging and pass the absolute Go executable
path through `bridge.py capture-wacom --sdk-adapter ...`, along with
verified synthetic signer IDs and explicit local operator confirmation.
The Python bridge launches Go, captures JSON without writing the pen data
to log files, validates it, and stores the encrypted result in SQLite.

This feature remains **staging-only and disabled by default**. A successful
build does not prove actual hardware connectivity or legally valid consent;
the operator must check physical STU-540 capture before any rollout.

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
