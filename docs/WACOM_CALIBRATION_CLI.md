# STU-540 local SDK calibration check

This CLI reads actual tablet X/Y/pressure maximums from the **official**
Wacom Linux SDK 2.16.1 `query` executable. The parser does not assume
unverified STU-540 dimensions. It only prints aggregate capability values;
no pen coordinates, signature evidence or borrower information are collected.

On the Ubuntu workstation, with other Wacom samples stopped:

```bash
cd ~/LoanHub-Wacom
git fetch origin
git switch feat/wacom-calibration-cli-20261104
git pull --ff-only
cd services/wacom-connector
go test ./... &&
go build -o loanhub-wacom-connector . &&
./loanhub-wacom-connector --calibration-test \
  --sdk-query="$HOME/wacom-stu-sdk/sdk-extracted/Linux/x86_64/query"
```

The executable receives no HTTP-controlled arguments. Its output is bounded
and the diagnostic terminates after 15 seconds. A missing device, missing
capability, or malformed/duplicate value fails closed.

**This is not yet a live capture or contract signing capability.** No
browser stream, backend upload, signing approval, evidence persistence,
or borrower consent verification is enabled by this flag.
