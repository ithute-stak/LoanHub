# Wacom STU-540 readiness vs contact diagnostics

The previous local test printed the SDK readiness line, then timed out
with 15 non-report output lines and zero pen reports. That means the Wacom
sample initialized, **not** that writing was captured.

The local Go diagnostic now counts and reports separate state:
- `sdk_ready`: whether the vendor sample printed its stylus-ready prompt
- `pen reports`: number of well-formed seven-number SDK lines
- `pen-contact reports`: number of numeric lines with ready=1 and switch=1

No pen coordinates, pressure, sequence numbers or timestamps are printed.
This remains a **disposable local test only**, not live signing or an
authenticated hardware capture service.

Run on the Ubuntu workstation:

```sh
cd ~/LoanHub-Wacom
git fetch origin
git switch feat/wacom-capture-readiness-diagnostics-20261104
git pull --ff-only
cd services/wacom-connector
go test ./... &&
go build -o loanhub-wacom-connector . &&
./loanhub-wacom-connector --pen-test \
  --sdk-pen-sample="$HOME/wacom-stu-sdk/sdk-extracted/Linux/x86_64/simpleInterface"
```

Repeat with `--stroke-test` after stopping the previous sample. For
both tests, place the pen on the tablet **after** the SDK-ready message,
keep it in contact, and draw multiple disposable strokes. No private
borrower signature should be drawn during this diagnostic.

If `sdk_ready=true` but `pen reports=0`, run the official
`simpleInterface` interactively again to isolate a vendor SDK
session/transport issue. Avoid changing USB permissions that already
work, and never open localhost diagnostics on external interfaces.
