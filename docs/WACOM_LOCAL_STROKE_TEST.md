# Local STU-540 stroke assembly diagnostic

This branch adds an **opt-in local-only** Wacom test path that connects the
previously verified official SDK simpleInterface report stream to LoanHub's
bounded in-memory stroke assembler. It distinguishes pen contact and pen lift,
and reports aggregate point/stroke counts only.

On the Ubuntu signing PC:

```sh
cd ~/LoanHub-Wacom
git fetch origin
git switch feat/wacom-local-stroke-test-20261104
git pull --ff-only
cd services/wacom-connector
go test ./... &&
go build -o loanhub-wacom-connector . &&
./loanhub-wacom-connector --stroke-test \
  --sdk-pen-sample="$HOME/wacom-stu-sdk/sdk-extracted/Linux/x86_64/simpleInterface"
```

Only draw **disposable test strokes** after the SDK-ready prompt. The
test runs for up to 25 seconds, keeps coordinates/pressure/timing in
process memory, and reports numeric report count, contact point count and
stroke count without printing, storing or uploading raw points.

This is not an SDK-backed secure device attestation, a network API, an
authenticated borrower signature, or a signed contract. Existing status
API still reports `connected:false`, and no upload or finalize routes
are introduced. Before real signing, implement vendor-supported capture
lifecycle, calibrated axes and pressure, authenticated workstation
identity, per-contract borrower consent and audit, secure channel and
server validation, encrypted evidence storage and signed PDF workflow.
