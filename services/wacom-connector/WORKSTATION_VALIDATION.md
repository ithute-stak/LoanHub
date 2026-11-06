# STU-540 physical PC validation — no VPS Wacom bridge

This test is run **on the Linux PC physically connected to the Wacom STU-540**.
It does not run on the LoanHub VPS.

The script checks the connector Go tests, official SDK sample executables,
USB device identity, and (with deliberate opt-in only) a disposable
handwriting-to-PNG test. It never accepts LoanHub credentials or sends
customer data to any service.

## Step 1 — Get the test code onto the actual workstation

In the existing local LoanHub repository checkout, fetch this branch after
the draft review is ready. Do not switch away from a dirty working tree.

```bash
git fetch origin test/wacom-real-workstation-readiness-20261106
git status --short
```

Use a **separate worktree** if the main workstation checkout has uncommitted
changes. After selecting the readiness branch, go to
`services/wacom-connector`.

## Step 2 — Run safe checks (no pen capture)

```bash
cd services/wacom-connector
bash -n scripts/workstation_readiness.sh
bash scripts/workstation_readiness.sh
```

Expected: Go tests pass; official Wacom sample binaries are executable; USB
vendor/product `056a:00a8` is found. This does not prove a working pen.

If the installed vendor paths differ, set the two paths explicitly:

```bash
export WACOM_SDK_QUERY="$HOME/wacom-stu-sdk/sdk-extracted/Linux/x86_64/query"
export WACOM_SDK_PEN_SAMPLE="$HOME/wacom-stu-sdk/sdk-extracted/Linux/x86_64/simpleInterface"
bash scripts/workstation_readiness.sh
```

## Step 3 — Test real pen strokes (disposable only)

Close any software already holding the STU-540, including another
`simpleInterface` or Wacom connector.

```bash
bash scripts/workstation_readiness.sh --hardware
```

The tool requires an interactive console and a typed `TEST` confirmation.
Use **meaningless scribbles only**. A successful result prints a PNG size,
sample counts and digest, but saves or uploads no handwriting.

## Interpreting the result

- **Go tests fail:** stop; fix the connector branch and rerun CI.
- **USB not detected:** inspect local cable, USB access and STU power.
- **SDK executable unavailable:** confirm vendor SDK installation and path.
- **Zero pen reports:** check the SDK is ready and not claimed by another
  process; do not interpret USB detection as capture success.
- **PNG rendered:** hardware read-to-image path has been exercised on
  this PC. It is *not* approval for real signature collection.

## Next required validation

With a disposable company/user/borrower dataset on a **controlled LoanHub
test API**, test operator login, tenant-scoped client lookup, preview, consent,
upload, independent review, and the exact-contract readiness endpoints.
Keep document finalization disabled until per-contract consent,
authorization, storage and audit requirements are proven.

Neither this script nor the draft PRs install a Wacom service on the VPS.
