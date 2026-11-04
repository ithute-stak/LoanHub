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
