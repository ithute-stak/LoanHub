# Wacom workstation possession proof — local-only CLI

The enrolled workstation can now sign a **genuine** LoanHub challenge
without exposing its private Ed25519 key to browser JavaScript or creating
a local HTTP signing oracle.

## Operator workflow (test only)

1. Prepare a pad session through the existing authenticated Contract Signing
   Centre. The operator must have a matching *active* workstation enrollment.
2. Using an authenticated LoanHub operator session, POST
   `/api/v1/contract-signing/contracts/{contract_id}/pad/sessions/{session_id}/workstation-challenges`
   with `{"workstation_id":"<enrolled-uuid>"}`. Store the short-lived
   JSON response locally with permissions preventing unauthorized reads.
3. On the enrolled workstation, use the local Go connector binary:

   ```sh
   loanhub-wacom \
      --sign-workstation-challenge=/secure/workstation-identity-dir \
      --proof-session-id=<session_uuid> \
      < /secure/backend-challenge.json > /secure/workstation-proof.json
   ```

   The command checks the expected session UUID, enrolled workstation ID,
   challenge ID, 32-byte nonce, fixed 30-second maximum lifetime, backend
   capture-disabled field and canonical protocol signature payload.
   It emits only `challenge_id`, `workstation_id`, and `signature_base64`.
   The private key never leaves the privately owned identity directory.
4. Submit those three JSON proof fields to the appropriate authenticated
   LoanHub API endpoint. The existing
   `/workstation-proofs` endpoint verifies and consumes the challenge but
   **does not issue a preview ticket**. The separate proof-bound
   `/preview-tickets` endpoint exists on draft PR #579 and must be
   integrated and independently verified before any preview can begin.

## Deployment restrictions

This command is intended to demonstrate real server/local-key protocol
compatibility, not general browser authorization. It requires an explicit
operator-selected session and an interactive local transfer of the
short-lived challenge. The private key must **never** be sent to a browser,
embedded in frontend code, or returned from the diagnostics listener.
Do not mount an arbitrary-challenge signing API in the localhost service.
No capture, websocket, evidence upload or contract signing is activated.
