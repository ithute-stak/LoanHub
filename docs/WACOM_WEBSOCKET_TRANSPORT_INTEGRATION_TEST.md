# STU-540 preview — actual WebSocket protocol regression test

This phase adds `authorized_preview_websocket_integration_test.go` in the
Go connector. Unlike earlier handler tests, it starts an in-process TCP
HTTP test server and performs a real Gorilla WebSocket upgrade.

The transport tests explicitly verify that:

1. A foreign browser Origin is rejected *before* the upgrade and before
   the backend authority is consulted.
2. The approved browser Origin can upgrade, but a missing preview ticket
   causes the connection to close with no frames and no backend request.
3. A syntactically bounded but unauthenticated ticket is passed once to
   the authority and denied. The connection closes without streaming any
   handwriting or invoking the SDK.

The tests do not substitute a mock signing backend or a fake SDK as a
production fallback. No real credentials or physical tablet are
required. They cover the transport admission boundary only and do NOT
constitute a successful physical handwriting test.

## Remaining supervised test

The actual end-to-end path still requires a real enrolled STU-540
workstation, trusted backend signer and mTLS certificates, the
dedicated TLS ingress topology, a backend-approved contract and short-
lived preview ticket, the official SDK executable and calibration,
and one supervised local capture lease. An operator must observe pen
strokes on the physical tablet and on the LoanHub browser **in the
same session**. Ticket revocation, cancellation and replay must also
be tested under real conditions.

The diagnostic service, opt-in proof-only mode and legal
contract-signing workflow have not been changed.
