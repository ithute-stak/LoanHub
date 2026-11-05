# Wacom protected operator test workflow (manual prototype)

The Contract Signing Centre now composes `WacomTestAuthorizationPanel`
inside `ContractPadPreflight` for an eligible prepared contract session, behind
`NEXT_PUBLIC_LOANHUB_WACOM_PREVIEW_UI=true`. Its backend operations are
operator-authenticated via LoanHub's ordinary API client.

## Explicit user steps

1. Enroll and approve the Wacom workstation in LoanHub beforehand.
   Provision its Ed25519 identity in a private local directory, and install
   trusted backend signing keys and a trusted mTLS client certificate
   according to the separate security setup.
2. Prepare a contract pad session and check current preview eligibility.
3. Enter the **enrolled workstation UUID** (a selector, never proof of
   identity) and choose **Request backend challenge**.
4. Copy the returned challenge JSON to an enrolled workstation. Sign the
   full JSON using the Go CLI (no private key ever enters JavaScript):

   ```sh
   loanhub-wacom \
     --sign-workstation-challenge=/secure/wacom-identity \
     --proof-session-id=<session_uuid> \
     < /secure/backend-challenge.json > /secure/workstation-proof.json
   ```

5. Paste the resulting proof JSON into the LoanHub panel and submit it to
   `POST /api/v1/contract-signing/contracts/{contract_id}/pad/sessions/{session_id}/preview-tickets`.
   Backend checks operator, tenant, challenge, enrolled workstation,
   expiry, and contract hash. Challenge use is atomic and one-time.
6. A successful response remains in ephemeral browser memory. One explicit
   click on the Wacom preview field sends it in the first WebSocket data
   frame; it is never placed in a URL. The WebSocket itself remains
   unmounted in the deployed diagnostics service.

**This manual 30-second challenge workflow is a protocol-validation
prototype, not a practical production UX.** Automated secure local
workstation handoff is still necessary before it can reliably be used
within the challenge and ticket expiration windows. No browser
cryptographic key material or general-purpose local signing endpoint
has been introduced.

## Safety boundaries

This new UI is hidden unless the test UI flag is enabled. The server
ticket issuer and connector introspection also default to disabled; the
connector has not been switched to live capture. Even with a valid
preview ticket, no contract is signed, no PDF is modified and no
handwriting evidence is stored. Existing pointer, wet-ink, electronic
and Email + OTP workflows remain unchanged.

The real ASGI TLS handshake metadata bridge, local protected mTLS
provisioning, trusted WebSocket route mounting and physical
STU-540-to-browser test remain explicit go-live blockers.
