# STU-540 local calibrated stroke test

Confirmed from the operator's official SDK `query` output, STU-540
firmware 01.08: tabletMaxX=10800, tabletMaxY=6480,
tabletMaxPressure=1023, screenWidth=800, screenHeight=480.
These values are **read again from the device**, not hardcoded in the
diagnostic. If the actual SDK values change or cannot be read, it fails
closed.

On the Ubuntu workstation that physically holds the tablet:

```sh
cd ~/LoanHub-Wacom
git fetch origin
git switch feat/wacom-calibrated-stroke-test-20261104
git pull --ff-only
cd services/wacom-connector
go test ./... &&
go build -o loanhub-wacom-connector . &&
./loanhub-wacom-connector --calibrated-stroke-test \
  --sdk-query="$HOME/wacom-stu-sdk/sdk-extracted/Linux/x86_64/query" \
  --sdk-pen-sample="$HOME/wacom-stu-sdk/sdk-extracted/Linux/x86_64/simpleInterface"
```

Close old Wacom test processes first. The official `query` program
opens the USB device, reads capabilities, and exits; the connector then
launches the official `simpleInterface` sample in a PTY. Only after
its ready prompt should you draw disposable test strokes, lifting the pen
between strokes. It runs for up to 25 seconds.

Valid raw strokes are assembled, transformed to LoanHub's 640x240 test
preview coordinate space and immediately discarded. Logs contain only
numeric totals: SDK reports, contact points, strokes and validated
preview points. **No image, coordinate sequence, customer signature,
contract data, network upload, or signed PDF** is created.

This is not yet live browser preview, authenticated borrower consent, or
a signing-ready hardware driver. Existing localhost status remains
diagnostics-only and existing email OTP signing is unchanged.

## Pen tuple ordering verified from physical STU-540 output

The vendor sample's displayed header is misleading. Observed numeric
rows such as `1 0 0 10091 4944 8160 1` map to
`ready=1, switch=0, pressure=0, x=10091, y=4944, time=8160, sequence=1`.
Parsing them as X/Y/pressure puts pressure at 4944, impossible for the
verified STU-540 maximum of 1023. The local parser has been corrected;
the raw device coordinate ranges are enforced separately during
calibrated validation.

A row with `switch=0, pressure=0` reflects pen proximity/hover, **not
confirmed pen-tip contact**. For contact, the official SDK should report
`switch=1` with positive pressure.

An SDK readiness prompt alone only proves initialization, not a capture.
If the Go diagnostic reports zero reports, check direct SDK output and
ensure no other Wacom process owns the tablet. No borrower signatures
should be used during tests.

## Confirmed transport issue — local interactive stdin

The operator demonstrated the official Wacom SDK through
`script -q -f -e -c ... /dev/null | awk ...`: at least 360 numeric pen
reports and 160 pen-contact reports arrived. This establishes that USB,
SDK, PTY and piped stdout can work together.

The Go launch previously replaced script's stdin with an inert `os.Pipe`,
which repeatedly yielded vendor startup lines but zero pen reports on
the workstation. The connector now inherits the calling **real terminal
stdin** for locally invoked diagnostics, matching the proven shell
pipeline. Noninteractive CI mock tests retain the open pipe fallback.

This is a candidate fix. It must still pass the operator's STU-540
calibrated stroke test; do not mark live capture complete from CI alone.
