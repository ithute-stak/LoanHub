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
