# Protected STU-540 preview route composition (unmounted)

`newProtectedWacomPreviewTestMux` is a new **composition-only** Go
helper that combines the local proof handler with the authenticated
`/v1/preview/stream` WebSocket handler. This is NOT wired to the
default `--diagnostics` mode or to `--preview-proof-test`, and it is
not deployed. It is intended for the later physically supervised
integration test.

It refuses to create an HTTP mux unless ALL of the following are
provided together:

- The locally enrolled workstation Ed25519 identity, loaded from a
  private connector-owned directory.
- Independently pinned backend Ed25519 signer key, identical to the
  explicitly configured set used for preview-ticket verification.
- A verified workstation UUID matching the key-bearing local identity.
- A configured backend mTLS introspection client and the protected
  replay directory needed for single-use ticket consumption.
- Valid SDK calibration and explicitly fixed vendor SDK executable path,
  through the existing protected authority constructor.

The WebSocket handler additionally enforces localhost Host, exact
Origin, first-frame signed-ticket authorization, independently
revalidated tenant/session/enrollment state, replay protection and
SDK source restrictions. None of those checks is bypassed by this
composition helper.

New Go tests cover missing backend authority, mismatched workstation
identity, substituted signing key, missing durable replay store,
untrusted Origin and attempts to upgrade without a WebSocket handshake.

**Still blocking a usable hardware test:** this composition helper is
not a running listener. Before wiring it into a supervised opt-in
listener, the actual TLS-terminating ASGI server must provide verified
client-certificate metadata; separately provisioned mTLS certificates,
backend signer/public key, enrollment, replay directory, real SDK
executable and calibration must be verified on the physical
workstation. Normal production diagnostics stay unchanged. Preview is
never consent or legal contract-signing evidence.
