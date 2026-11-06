# Wacom — local response to an authenticated LoanHub challenge

The workstation identity setup and the tenant-controlled registration,
approval, and challenge APIs already exist on `main`. This phase adds
the missing **manual** challenge-response command to the Go CLI.

This is a development diagnostic, not a browser endpoint and not an
automated API login. A separately authenticated operator must request
the challenge from the LoanHub backend. Do not obtain challenges from
untrusted websites, emails or unauthenticated devices.

## Workstation procedure

After installing and registering the local identity, use a disposable
unsigned test contract and an authenticated enrolled operator.

1. Request a 30-second challenge from the HTTPS LoanHub API:
   `POST /api/v1/contract-signing/contracts/{contract_id}/pad/sessions/{session_id}/workstation-challenges`.
   Request body: `{"workstation_id":"<approved-device-UUID>"}`.
2. Immediately pass the exact JSON response on stdin to the CLI:

   ```bash
   cd ~/LoanHub-Wacom/services/wacom-connector
   ./loanhub-wacom-connector --respond-workstation-challenge="$HOME/.local/share/loanhub-wacom" < /path/to/restricted-challenge.json
   ```

   This outputs a JSON proof with `challenge_id`,
   `workstation_id`, and `signature_base64`. It **does not**
   reveal the local private key. Restrict challenge/proof files to mode
   0600 and delete them after the test. Do not put secrets or customer
   data in shell history or public paste logs.
3. Send the proof JSON over an authenticated LoanHub session to
   `POST /api/v1/contract-signing/contracts/{contract_id}/pad/sessions/{session_id}/workstation-proofs`.

The 30-second expiry applies to the entire exchange; expired requests
must be retried with a fresh challenge. A different workstation ID,
malformed nonce, incorrect session, malformed JSON, oversized input or
`capture_enabled:true` is rejected. The response is still
`capture_enabled:false`; successful key proof is **not** signing
permission.

## Remaining work

- Authenticated end-to-end operator UX / trusted workstation client
  transport, with HTTPS-only session handling and proper audit logs
- Hardware-enforced key handling and enrollment lifecycle hardening
- Backend ticket issuance and live revocation protocol
- An authenticated localhost pen-capture endpoint and browser preview
- Physical end-to-end tests and separate legal evidence/PDF controls.

Do not put the private key into GitHub, Docker images or the VPS.
Existing diagnostics and email-OTP signing are unchanged.
