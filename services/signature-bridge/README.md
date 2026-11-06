# LoanHub Signature Bridge — offline-first starter

This is a **staging-only foundation**, not yet a completed desktop application or a signing system.

## Local signing review window (staging prototype)

A first local desktop review window is available using Python Tkinter.
Launch it from an **interactive graphical Linux terminal** attached to the STU-540:

```bash
cd services/signature-bridge
LOANHUB_SIGNATURE_BRIDGE_MODE=staging .venv/bin/python review_dialog.py \
  --sdk-adapter "$PWD/../wacom-connector/loanhub-wacom-connector"
```

If Tkinter is missing, install the distribution's `python3-tk` package.
Use **test strokes only**. Click **Start signing**, wait for native capture to
complete, and inspect the locally rendered preview. **Reject signature**
discards the preview, and **Clear / Restart** discards the prior capture and
starts a new 25-second SDK session. This is a **software reset**, not a
guarantee that the physical STU-540 display was erased. A hard USB/tablet
clear command has not been certified.

The National ID field is masked and remains in volatile GUI memory only.
The previous synthetic suggestion dropdown has been removed. Real client lookup is exact-match only and requires authenticated staging configuration; no plaintext customer directory is stored locally.
Basic input hygiene is **not** National ID verification. Phone numbers are
not part of the new UI. Real client identification will require an
authenticated, tenant-scoped LoanHub National ID lookup; never substitute a
manually entered National ID for an authenticated borrower UUID.

**Post to VPS is deliberately disabled** until the server supports
authenticated National ID resolution, explicit operator authorization and
consent evidence, per-tenant policies, duplicate-source protection, and
staging acceptance testing. This window does not read or alter the existing
two stored offline test captures and does not create a local queued record.
It is not yet an automatically triggered modal in the LoanHub web portal;
that needs a separate authenticated desktop launch/handshake protocol.

## Offline lookup configuration preflight

Before attempting any real client lookup, check whether the desktop has a
private staging lookup configuration:

```bash
cd services/signature-bridge
.venv/bin/python lookup_preflight.py
```

The command **never accesses a network, executes a token provider or prints
customer IDs/credentials**. Exit code 0 means local profile metadata passed
validation only; exit code 2 means the profile is missing or unsafe.
It does **not** prove the staging server is deployed or authorize a client
lookup. Live `api.loanhub.co.ls`, `www.loanhub.co.ls` and `loanhub.co.ls`
hosts are rejected by the staging client. A reviewed staging HTTPS hostname,
operator access and server deployment remain mandatory.

## Independent staging feature gates

The read-only exact National ID lookup and the quarantined signature import
inbox have **separate, fail-closed switches**:

- `LOANHUB_SIGNATURE_BRIDGE_LOOKUP_ENABLED=true` enables authenticated
  staging lookup only (still subject to role/tenant controls and audit limit).
- `LOANHUB_SIGNATURE_BRIDGE_IMPORT_ENABLED=true` enables the staging import
  inbox separately. Keep it **false** for identity lookup rollout.
- Both routes are disabled unless `ENVIRONMENT=staging`. Neither switch
  authorizes capture, signature reuse or contract signing.

Do not deploy the previous image `loanhub-wacom-signature-bridge:77d65918`
to activate lookups: it predates this separation and enabling its old shared
switch would also open the quarantine import route. Rebuild a uniquely tagged
image from the latest feature branch and complete CI before staging cutover.

## Authenticated National ID rate limiting (staging)

The backend now reserves each exact National ID lookup attempt through
the existing PostgreSQL-backed audit ledger, guarded by a tenant- and
operator-specific transaction advisory lock. Staging policy permits at most
**8 lookups in a rolling 60-second window** per authenticated operator and
company. This limits concurrent guessing even across separate API workers.

Audit events record **only the operator, company and lookup action**:
not the National ID, person name, bearer token, signature image or raw body.
If the database audit service cannot respond, the endpoint refuses lookup
with HTTP 503. Exhausted budgets return HTTP 429. Logging limits are
complementary to authentication; real lookup remains disabled until
endpoint deployment, tenant authorization and integration tests pass.
Neither a match nor a successful lookup grants capture/reuse/contract
signing rights.

## Visible National ID and persistent local watcher (no demo mode)

The desktop National ID entry is now **plain text**, not a password field.
The synthetic DEMO/TEST dropdown has been removed. When an authorized
staging lookup profile is configured, the operator can type an exact
National ID and see the matching client's full name and existing-signature
status. Lookup requires authenticated, tenant-scoped LoanHub access;
no real client records are cached in the workstation.

The local watcher is registered as a GNOME graphical-session autostart
and can reopen the review window when the operator touches the STU pad.
This starts after graphical login following reboot, **not before login**,
because the official Wacom SDK relies on an interactive TTY. It uses
Ptyxis or GNOME Terminal to provide that TTY. A completely headless
system boot watcher requires a separately validated SDK integration.

For authenticated staging lookup, an administrator must first create a
private `~/.config/loanhub-signature-bridge/lookup.json`, owned by the
desktop user and mode 0600. It contains only a **reviewed staging** URL,
the authorized company UUID and the absolute path to an owner-only
short-lived token helper (mode 0700), **never a token**:

```json
{
  "url": "https://APPROVED-STAGING-HOST/api/v1/signature-bridge/lookup-national-id",
  "company_id": "AUTHORIZED-STAGING-COMPANY-UUID",
  "token_provider": "/home/USER/path/to/reviewed-token-helper"
}
```

The file is **not generated with fake credentials**. The administrator
must validate the staging endpoint deployment, operator authentication,
permission scoping, audit and request rate limits before enabling lookup.
Without this file, the dialog displays a disconnected state and does
not search client data or accept new signatures.

Install or refresh the startup entry after configuring the profile:

```bash
.venv/bin/python install_review_autostart.py --install
```

All capture/posting and signature reuse remain disabled for real
clients until a separate consented session and server-side approval
process is in place; matching a client is not permission to reuse a
signature or sign a contract. The local two-item encrypted test queue
is not touched.

## National ID borrower match and signature reuse status (staging only)

A new authenticated `POST /api/v1/signature-bridge/lookup-national-id`
endpoint returns **exact** National ID matches only, scoped to the active
LoanHub company and limited to staff roles with lending/management permission.
It joins `Person.national_id` to the company-owned borrower account,
returns the official full name, and checks the existing
`BorrowerSavedSignature` registry and quarantined `SignatureBridgeImport`
records for the same borrower and company.

Status values include `existing_signature`, `pending_signature_review`,
`matched_no_signature`, `not_found` and `conflict`.
**None of these states grants new signing or reuse.** Active saved signatures
block recapture; reuse on a contract requires independently approved identity,
fresh document-specific consent, a valid contract hash and a separate authorized
signing session. Pending review blocks recapture as well.

The desktop dialog can be configured to request these matches after the
operator enters an exact ID (debounced) using a short-lived token provider.
It does not store National IDs or tokens, and it fails closed when lookup
fails. This requires an **authorized, deployed staging server**, an explicitly
verified staging HTTPS URL and an independently provisioned private
operator-token helper. Neither is created by this PR. Do not configure the
production hostname or reuse production tokens. Real-client capture remains
disabled in authenticated-lookup mode until a verified consent workflow is
available.

```bash
LOANHUB_SIGNATURE_BRIDGE_MODE=staging .venv/bin/python review_dialog.py \
  --sdk-adapter "$PWD/../wacom-connector/loanhub-wacom-connector" \
  --lookup-url https://APPROVED-STAGING-HOST/api/v1/signature-bridge/lookup-national-id \
  --company-id AUTHORIZED-STAGING-COMPANY-UUID \
  --token-provider /absolute/path/to/reviewed-private-token-helper
```

The above values are examples, **not instructions to use production
credentials**. No actual staging endpoint has been verified or deployed
as part of this phase. A production user must not be searched from
the workstation UI until staging authorization and protections against
ID enumeration (including rate limits and audit trails) have been reviewed.

## Faster signing preview and pen-contact GNOME autostart (staging only)

The review dialog's test capture now uses a shorter **10-second native SDK
window** instead of the original 25-second window; timing and SDK startup
remain hardware-dependent. The underlying 25-second diagnostic CLI is unchanged.

The experimental **pen-contact watcher** runs in a real local terminal and
processes only a boolean first-pen-down indication. It does not save the
wake-up gesture, expose coordinates, open a port, or send anything to LoanHub.
On contact it opens the previously hidden review window. **The initial touch
only wakes the dialog**: the operator must press **Start signing** and make a
NEW disposable test signature before a preview is produced. While the dialog
is open, the watcher does not contend with the tablet. Closing the review
window in auto-watch mode hides it and resumes the watcher.

From a graphical GNOME terminal, after a fresh Go build, test manually:

```sh
cd services/wacom-connector
go test ./...
go build -o loanhub-wacom-connector .
chmod 755 loanhub-wacom-connector
cd ../signature-bridge
LOANHUB_SIGNATURE_BRIDGE_MODE=staging .venv/bin/python review_dialog.py \
  --sdk-adapter "$PWD/../wacom-connector/loanhub-wacom-connector" --auto-watch
```

To register startup **after GNOME desktop login following reboot**, opt in
with this command (do not run under sudo):

```sh
.venv/bin/python install_review_autostart.py --install
```

This creates a private `~/.config/autostart/loanhub-staging-signature-review.desktop`
entry which launches a **visible Ptyxis / GNOME Terminal** to supply the controlling
TTY required by the vendor Wacom SDK. The app starts hidden and listens for
pen contact until the first touch. No display can be shown before a user
logs into the graphical session. A terminal remains open while monitoring,
and the SDK may take several seconds to become ready. Stop the terminal
process to pause monitoring. To disable login startup:

```sh
.venv/bin/python install_review_autostart.py --remove
```

The watcher and faster capture are **not yet device-certified** and require
on-device testing. Physical STU pad display clearing is not implemented;
Clear/Restart only resets the local preview and capture. Posting to VPS,
client National ID verification, contract signing and automatic signing
remain disabled. The existing encrypted capture queue is not modified.

## Staging import preflight (offline by default)

Before connecting a workstation to a staging import service:

```bash
LOANHUB_SIGNATURE_BRIDGE_MODE=staging .venv/bin/python bridge.py staging-import-preflight
```

This command only queries local queue counts. It performs **zero network requests**
and reports `ready_to_sync: false` until an independent staging
certification is completed. A disposable reference does not constitute
independently verified identity or consent. The two captured workstation
examples are to remain offline. The explicit `sync` CLI now rejects any
environment other than `LOANHUB_SIGNATURE_BRIDGE_MODE=staging`, but
staging mode alone is **not** approval to upload captures. For server
integration, use an isolated synthetic fixture, verified tenant-scoped
authentication, PostgreSQL isolation and replay tests.

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

## Verify a disposable local capture without viewing handwriting

After an operator-supervised staging capture, the bridge prints a
`signature_id`. Verify the encrypted vault entry locally without exposing
coordinates or sending anything to LoanHub:

```sh
LOANHUB_SIGNATURE_BRIDGE_MODE=staging \
  .venv/bin/python bridge.py verify-local-capture \
  --signature-id UUID-PRINTED-BY-CAPTURE
```

The command verifies that the stored encrypted payload decrypts to a
valid bounded stroke envelope, and reports only the stroke/point counts,
local queue state and disabled signing status. It **does not** certify
the physical device or the operator's identity/consent assertions.
Do not share captured raw JSON, cryptographic keys or customer details.

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
The operator now sees the native adapter's redacted `Wacom SDK ready` cue
on stderr and should begin disposable strokes only after that message.
The Go adapter counts, but does not forward, vendor stderr; its stdout
contains private pen JSON and is captured separately from terminal output.

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
