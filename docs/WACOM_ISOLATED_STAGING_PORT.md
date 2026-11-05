# Wacom protected staging server — port isolation test

A new explicit Go flag `--protected-preview-staging=/absolute/private/config.json`
loads the existing staging preflight configuration, constructs the
protected backend-mTLS WebSocket authority and proof handler, and binds
a **separate local-only** HTTP test server to
`127.0.0.1:8766`. The normal `127.0.0.1:8765` diagnostics service
and systemd unit remain untouched.

**This isolated server is NOT a working browser handwriting endpoint.**
Its protected WebSocket handler still enforces the production port and
Host `127.0.0.1:8765`, so browser attempts against port 8766 are
rejected. This is intentional while staging mTLS ingress remains
unavailable. It is not appropriate to weaken the exact Host or Origin
checks to make the staging endpoint accept arbitrary traffic.

Start the new binary *only after* locally provisioned keys, certificates,
enrollment and SDK have passed the offline preflight:

```sh
./loanhub-wacom-staging --staging-preflight=/absolute/private/preflight.json
./loanhub-wacom-staging --protected-preview-staging=/absolute/private/preflight.json
```

The second command listens until terminated and should only be used in
an attended test session. No service file is installed or modified.
A missing/untrusted key, malformed configuration, invalid SDK path,
failed calibration or missing replay directory prevents startup.
The mTLS backend client will still fail closed if the real backend
does not accept the provisioned workstation certificate.

The next practical requirements are a secure production-like staging
mTLS ingress that authenticates the workstation certificate, approved
workstation enrollment and signed short-lived preview tickets, and a
supervised process changeover to the exact browser connector port.
The user has independently observed SDK calibration X=10800,
Y=6480, pressure=1023 and a successful local capture of 60 SDK reports,
16 contact points, 1 stroke and 16 valid preview points. **Live
tablet-to-browser streaming remains unverified.**
