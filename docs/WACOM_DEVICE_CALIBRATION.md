# Wacom STU-540 calibration and preview coordinates

The official Wacom SDK emitted 353 native numeric pen reports in a verified
Ubuntu workstation test. The STU-540's raw coordinate and pressure maxima
have **not yet been established from its live vendor capabilities**; avoid
hardcoded guesses or treating observed maximum values as device bounds.

This change adds a Go-only pure transformation:
- Requires explicit, positive calibrated X/Y bounds and maximum pressure.
- Maps X into [0,640] and Y into [0,240], matching the existing browser
  preview and backend candidate-validation canvas.
- Normalizes pressure into [0,1] and device time relative to the first
  contact, preserving stroke segmentation.
- Rejects out-of-range points, incorrect ordering, repeated sequence,
  empty or over-budget strokes, and invalid duration.
- Uses synthetic device bounds **only in unit tests**, not production.

Security boundaries: no HTTP route, no export or persistence of raw
handwriting, no automatic vendor-device authentication, no loan signing.
This function MUST be called only after future SDK code has supplied
the actual, verified device dimensions; it cannot be invoked with
browser-supplied calibration.

Next: read the installed Wacom SDK documentation/verified capabilities
for STU-540 maximum X, Y, pressure and report timing/sequence semantics.
Then integrate a secure, authenticated capture stream and a test-only
canvas preview with strict session binding and short expiration.
