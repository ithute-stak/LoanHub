# STU-540: Disposable physical pen-to-PNG test (Phase 4)

**Runs on the operator's Linux workstation, never on the VPS.**
This milestone reads only the installed Wacom vendor SDK samples already
used by the connector's local diagnostics, calibrates tablet coordinates,
and renders a bounded PNG in RAM. The preview is discarded when the process
exits. Nothing is persisted, signed or uploaded.

## Test on the workstation

Make sure the existing Wacom SDK samples `query` and
`simpleInterface` are installed and executable. Close any other program
using the tablet.

```sh
cd services/wacom-connector
go test ./...
go build -o loanhub-wacom-connector .
./loanhub-wacom-connector --disposable-png-test \
  --sdk-query="$HOME/wacom-stu-sdk/sdk-extracted/Linux/x86_64/query" \
  --sdk-pen-sample="$HOME/wacom-stu-sdk/sdk-extracted/Linux/x86_64/simpleInterface"
```

**Draw only disposable test strokes** on the STU-540. Never sign with a real
client or operator during this diagnostic. The test has a 25-second SDK read
limit. It verifies that pen reports can be converted to a nonempty PNG and
prints only size, contact/stroke counts and SHA-256 (not actual coordinates,
PNG bytes or client data).

The Go renderer uses 640 × 240 output, verifies device-calibration bounds,
requires actual pen movement, prevents accidental straight-line joins across
pen-up events, limits to 5,000 reports, and caps PNG size to 128 KB.

## Not yet live

- The local PC login/client lookup UI at `127.0.0.1:8767` still has no capture endpoint.
- The test cannot upload files or execute signed contracts.
- A separate authenticated, consent-confirmed operator-initiated capture
  flow is required before sending any image to the draft LoanHub API.
- The SDK pipeline is presently a vendor sample process, not a reviewed
  permanent device driver. A physical workstation test is required.
- PRs #586/#587/#588 and this change remain separate draft milestones.
