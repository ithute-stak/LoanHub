package main

// Authorized *test-only* pen-to-preview coordinator. It has no HTTP
// endpoint, does not make PDFs, and never saves handwriting. The caller must
// supply actual backend-backed enrollment and revocation adapters.
import (
    "context"
    "errors"
    "time"
)

// previewPenSource may only be an approved SDK adapter. Implementations must
// stop the vendor capture subprocess on ctx cancellation or deadline.
type previewPenSource interface {
    CollectPreview(ctx context.Context, onPen func(penSample) error) error
}

// previewFrameSink is an authenticated, in-memory transport for test preview.
// Future implementation must verify the destination browser's current
// session, contract and origin, and never persist frames.
type previewFrameSink interface {
    DeliverPreview(ctx context.Context, scope previewTicketScope, strokes [][]previewPoint) error
}

type authorizedPreviewConfig struct {
    Admission previewAdmissionDependencies
    Calibration deviceCalibration
    Source previewPenSource
    Sink previewFrameSink
    MaxDuration time.Duration
}

// runEphemeralAuthorizedPreview authenticates before touching the SDK, limits
// recording to the ticket's expiry, continuously rechecks revocation, and
// transmits no strokes unless all checks still pass after capture. No live
// streaming is enabled by this purely dependency-injected primitive.
func runEphemeralAuthorizedPreview(
    ctx context.Context, ticket string,
    expected previewTicketScope, now time.Time,
    config authorizedPreviewConfig,
) error {
    if ctx == nil || config.Source == nil || config.Sink == nil ||
        config.MaxDuration <= 0 || config.MaxDuration > 20*time.Second ||
        !config.Calibration.valid() {
        return errors.New("Wacom preview capture not configured")
    }
    if ctx.Err() != nil { return ctx.Err() }
    // Verify the trusted signer and expiry before parsing any captures.
    claims, err := verifyPreviewTicketSignatureAndScope(
        ticket, config.Admission.Keys, expected, now,
    )
    if err != nil { return err }
    if err := admitTemporaryWacomPreview(ticket, expected, now, config.Admission); err != nil {
        return err
    }
    expiry := time.Unix(claims.ExpiresAt, 0)
    remaining := time.Until(expiry)
    if remaining <= 0 { return errors.New("preview ticket expired before SDK access") }
    duration := config.MaxDuration
    if remaining < duration { duration = remaining }
    bounded, cancel := context.WithTimeout(ctx, duration)
    defer cancel()

    var buffer localStrokeBuffer
    defer buffer.discard()
    // At most once per half-second (and at both ends), the active enrollment
    // and backend session must remain valid. A future adapter should offer a
    // push-revocation/cancel signal; this polling is not instant revocation.
    lastCheck := time.Time{}
    checkActive := func(force bool) error {
        if err := bounded.Err(); err != nil { return err }
        if !force && !lastCheck.IsZero() && time.Since(lastCheck) < 500*time.Millisecond {
            return nil
        }
        if config.Admission.Session == nil || config.Admission.Enrollment == nil {
            return errors.New("missing Wacom revocation authority")
        }
        if err := config.Admission.Session.CheckPreviewActive(expected); err != nil {
            return errors.New("Wacom preview session no longer active")
        }
        workstation, err := config.Admission.Enrollment.AuthenticatedWorkstationID()
        if err != nil || workstation != expected.WorkstationID {
            return errors.New("Wacom workstation enrollment no longer active")
        }
        lastCheck = time.Now()
        return nil
    }
    if err := checkActive(true); err != nil { return err }
    err = config.Source.CollectPreview(bounded, func(report penSample) error {
        if err := checkActive(false); err != nil { return err }
        return buffer.accept(report)
    })
    if err != nil { return err }
    if err := checkActive(true); err != nil { return err }
    strokes, err := buffer.finish()
    if err != nil { return err }
    calibrated, err := toPreviewStrokes(strokes, config.Calibration)
    if err != nil { return err }
    if err := checkActive(true); err != nil { return err }
    // Sink must enforce trusted browser session and must not persist points.
    return config.Sink.DeliverPreview(bounded, expected, calibrated)
}

