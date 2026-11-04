# Wacom STU-540: obtain actual SDK calibration

The official Wacom Linux STU SDK 2.16.1 tarball contains the vendor
`Linux/x86_64/query` executable. Inspection of this supplied binary confirms
the field names `Capability.tabletMaxX`, `Capability.tabletMaxY`, and
`Capability.tabletMaxPressure`. The Go parser added here accepts only
unambiguous, positive, bounded integers for all three; test numbers are
synthetic and **not STU-540 measurements**.

On the Ubuntu Wacom workstation, stop any prior simpleInterface process
and run this official SDK command:

```bash
"$HOME/wacom-stu-sdk/sdk-extracted/Linux/x86_64/query"
```

Do not use customer handwriting or personal information. Copy only the
three `Capability.tabletMax*` lines and the `Information.modelName` line
if printed. If the query sample displays different formatting, update and
test this parser against its real field format before use.

The current parser is deliberately pure and not wired to an HTTP handler
or the native stream. A production device-capability probe must also
authenticate the workstation, verify the SDK's attached device identity
and USB VID/PID, honor query timeouts and bind signed-session provenance
before permitting previews.

Contract signing, PDF finalization, raw signature export and reuse remain
disabled. Browser-supplied calibration values are never trusted.
