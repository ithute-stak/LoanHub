# Wacom STU-540 staging readiness — local, non-capture preflight

The Go connector now offers a separate `--staging-preflight` command
that **does not open a network listener, connect to the backend, access
USB, run the SDK, issue a ticket, or sign a contract**. It only verifies
that an enrolled workstation is structurally provisioned for a later,
supervised authenticated test.

The operator supplies an absolute, owner-readable JSON configuration
file (0600). Example placeholders (paths must exist on the test
workstation; do not commit real keys or certificate files):

```json
{
  "identity_directory": "/secure/wacom-test/identity",
  "trust_bundle_path": "/secure/wacom-test/identity/preview-trust.json",
  "replay_directory": "/secure/wacom-test/replay",
  "backend_ca_path": "/secure/wacom-test/identity/trusted-server-ca.pem",
  "client_certificate_path": "/secure/wacom-test/identity/workstation-client-cert.pem",
  "client_key_path": "/secure/wacom-test/identity/workstation-client-key.pem",
  "sdk_executable": "/usr/local/libexec/wacom/simpleInterface",
  "calibration_max_x": 10800,
  "calibration_max_y": 6480,
  "calibration_max_pressure": 1023
}
```

The calibration numbers above are **illustrative only** and MUST be
replaced with values actually read from the physical STU SDK tablet
capabilities. A syntactically valid calibration is not a verification
that the currently connected hardware reports these capabilities.

Run the standalone test build without changing the existing systemd
service:

```sh
./loanhub-wacom --staging-preflight=/secure/wacom-test/preflight.json
```

The command fails closed if the protected workstation identity, backend
challenge-signing key, preview ticket signing trust bundle or durable
replay directory is missing or incompatible. It also requires an
executable SDK file, structurally valid calibration, TLS client keypair,
configured trusted backend CA and a hardened backend HTTPS client using
TLS 1.3 and mandatory client-certificate settings. Configuration and
credential files must be owned, regular files (not symlinks), with
restrictive permissions.

**A local PASS is not a deployment approval.** It does not prove the
current mTLS backend endpoint is reachable, that the server trusts the
client certificate, that the real workstation enrollment is active, or
that the physical STU-540 can stream to the browser. Do not interpret it
as a legal signing result. To reach a genuine live preview, complete
server-side mTLS staging ingress, independently verify the actual SDK
calibration, enable the protected listener only in supervised staging,
and prove the complete tablet-to-browser stream with cancellations and
revocation tests.
