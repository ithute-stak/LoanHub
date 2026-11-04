# LoanHub Wacom workstation connector — diagnostics foundation

This is a **diagnostics-only** Go executable, not a functioning Wacom hardware driver.
It always returns `connected:false` and cannot collect signatures or finalize contracts. On Linux, it can identify USB device ID `056a:00a8` (STU-540) as `usb_detected:true` without claiming that the device is usable for signing.
No Wacom SDK, USB driver or native capture library is bundled.

## Build and test on the signing workstation

Requires Go 1.23+:

```sh
cd services/wacom-connector
go test ./...
go build -o loanhub-wacom-connector .
./loanhub-wacom-connector --diagnostics
```

The service binds only to `127.0.0.1:8765`. In another shell:

```sh
curl -i http://127.0.0.1:8765/v1/device/status
```

Expected when the STU-540 is plugged in: `{"protocol":"loanhub-wacom-v1","connected":false,"model":"STU-540","usb_detected":true}`. Without an attached STU-540, `usb_detected` is `false` and `model` is omitted.

Only `https://loanhub.co.ls` is accepted as a browser Origin; no origin is allowed for direct local diagnostics. No raw pen data, device IDs, customer information or contract details leave the workstation.

## Not production hardware-ready

The web app currently probes `http://127.0.0.1:8765`. Some HTTPS browsers can block access to a local HTTP service due to browser private-network access rules; this must be validated on the actual workstation before this can be relied on.

Next, confirm Wacom pad model, desktop operating system and vendor SDK. Then add driver-mediated detection, short-lived backend-authenticated capture, explicit informed consent, protected evidence submission and atomic PDF finalization, with security review and tests before enabling any signing actions.

## Official SDK integration prerequisite (STU-540 on Ubuntu)

Wacom's supported Linux integration uses the official STU SDK with libusb.
The installed SDK and its license must be obtained by the workstation administrator
from Wacom's Developer Dashboard; this repository intentionally does not bundle
or reverse-engineer any proprietary Wacom binaries.

On the **staff workstation** (never the LoanHub VPS), install build dependencies:

```sh
sudo apt-get update
sudo apt-get install -y libusb-1.0-0-dev libssl-dev
```

Follow the *exact* SDK version's official installation instructions for the
native library and least-privilege USB permissions. Do not open port 8765 on
any network interface or install broad world-writable udev rules as a shortcut.
The Go connector currently reads USB identity from Linux sysfs only; until a
reviewed SDK adapter is implemented, `connected` MUST remain `false`.

The LoanHub browser app distinguishes `usb_detected` from SDK connectivity:
USB presence cannot authorize a signature, identity proof or legal completion.

## Optional official SDK enumeration (STU-540, Ubuntu)

The workstation administrator has verified Wacom STU SDK 2.16.1 and its
`getUsbDevices` example can enumerate `056a:00a8:0108`. To let LoanHub
show that *additional diagnostic*, stop the old connector (Ctrl+C), then:

```sh
cd ~/LoanHub-Wacom
git fetch origin
git switch feat/wacom-sdk-enumeration-20261103
git pull --ff-only
cd services/wacom-connector
go test ./...
go build -o loanhub-wacom-connector .
./loanhub-wacom-connector --diagnostics \
  --sdk-enumerator="$HOME/wacom-stu-sdk/sdk-extracted/Linux/x86_64/getUsbDevices"
```

From another terminal on the same workstation:

```sh
curl http://127.0.0.1:8765/v1/device/status
```

Expected when the STU-540 is present and the SDK sample enumerates it:

```json
{"protocol":"loanhub-wacom-v1","connected":false,"model":"STU-540","usb_detected":true,"sdk_detected":true}
```

`sdk_detected` is a **startup snapshot**, not proof of an open SDK session or
available pen input. Restart after unplugging/replugging to refresh the SDK
snapshot. If the executable is absent, fails, times out or reports another
device, the status remains `sdk_detected:false`. The executable must be the
vendor-provided SDK sample on disk: no SDK binary is checked into GitHub.
`connected` remains `false` until a separately audited capture implementation
exists. The service runs on the Ubuntu desktop, not the VPS.

## Local pen communication diagnostic (no signing)

After building the connector on the Ubuntu PC, close any other sample
application using the STU-540, then run the **one-shot** native hardware test:

```sh
cd ~/LoanHub-Wacom
git fetch origin
git switch feat/wacom-local-pen-sample-20261104
git pull --ff-only
cd services/wacom-connector
go test ./...
go build -o loanhub-wacom-connector .
./loanhub-wacom-connector --pen-test \
  --sdk-pen-sample="$HOME/wacom-stu-sdk/sdk-extracted/Linux/x86_64/simpleInterface"
```

Draw only disposable test strokes when prompted. The test runs for **eight
seconds**, shuts down the vendor sample and prints only how many numeric pen
reports were observed. It does not return raw coordinates, pen pressure,
a reusable signature, images, or contract data. It does not contact the
LoanHub backend or create any signing session. It requires no VPS changes.

The binary uses an absolute path to the Wacom-supplied sample. This is a
development diagnostic and not a supported SDK adapter for production. If
the vendor SDK buffers its output when piped, you might see zero reports
despite working pen hardware; we will then need to link the documented
native SDK directly. Do **not** use this feature to sign real borrower
contracts or store test strokes as signatures.
