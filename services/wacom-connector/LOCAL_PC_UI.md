# Local Wacom PC operator interface

This desktop-facing UI is served **on the staff computer only**, by the
existing Go Wacom connector. It does not run on the VPS.

## Run locally (development, capture disabled)

Use Go 1.23+, a current LoanHub API test deployment with draft API PR #586,
and your official company UUID. Do **not** enter live customer details in a
test environment.

```sh
cd services/wacom-connector
go test ./...
go build -o loanhub-wacom-connector .
./loanhub-wacom-connector --pc-ui --loanhub-origin=https://YOUR-TRUSTED-LOANHUB-API-ORIGIN
```

Open `http://127.0.0.1:8767/` in the browser **on the same computer**.
The Go server listens only on TCP IPv4 loopback, not on the LAN.
No operator password, JWT or signature is saved to disk by this UI.

### Screen flow

1. Log in using LoanHub phone, password, optional authenticator code and
   an active LoanHub company ID.
2. The app requests the operator's signature status. Missing status displays
   a warning; it **does not** enable Wacom capture.
3. Search for a customer by National ID. The backend checks tenant and branch.
   If matched, the name, borrower ID and signature status are displayed.
4. The physical capture panel remains disabled until an official STU-540
   SDK adapter, consent review and downstream document authorization exist.
5. Sign out to erase the access token, operator status and customer result
   from the application's in-memory session.

### Security

The UI requires a 20-minute session cookie, POST-only operations, a random
CSRF token, exact browser Origin matching and exact local Host validation,
while rejecting iframe embedding and caching. Backend HTTPS redirects are
not followed. The Go client holds only short-lived access tokens in memory.
Never port-forward, proxy or expose the loopback listener publicly.

The original `--diagnostics` behavior at `127.0.0.1:8765` remains unchanged.
Do **not** enable capture or sign real agreements in this milestone.

### Remaining work

- Add an approved official Wacom STU SDK pen-to-image capture adapter
- Implement authenticated capture session and consent confirmation
- Verify/activate saved signature after correct identity evidence
- Connect authorized LoanHub document-signing flows
- Test on the real workstation and check accessibility and security controls
