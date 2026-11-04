package main

// A fail-closed authorization coordinator for future Wacom temporary previews.
// This is NOT an HTTP endpoint, does not talk to a signing pad, and does not
// enable legal contract signing. Browser-provided identifiers are not trusted.
import (
    "crypto/ed25519"
    "errors"
    "fmt"
    "time"
)

// previewEnrollmentProvider must return identity derived from a separately
// authenticated, enrolled workstation, NOT a token claim or HTTP body.
// A production adapter must enforce backend enrollment revocation and
// transport authentication; no default/allow-all provider is included.
type previewEnrollmentProvider interface {
    AuthenticatedWorkstationID() (string, error)
}

// previewSessionAuthority must retrieve current tenant/operator/contract
// state from the authenticated backend and check that the exact session
// remains preview-eligible, including up-to-date revocation.
type previewSessionAuthority interface {
    CheckPreviewActive(scope previewTicketScope) error
}

type previewAdmissionDependencies struct {
    Keys map[string]ed25519.PublicKey
    Enrollment previewEnrollmentProvider
    Session previewSessionAuthority
    Replay previewTicketReplayStore
}

// admitTemporaryWacomPreview first verifies trusted workstation identity,
// current backend session status, cryptographic ticket and durable single-use
// JTI. It then rechecks revocation after consuming the ticket. On any
// failure no local lease or capture stream is created.
func admitTemporaryWacomPreview(
    ticket string,
    expected previewTicketScope, // independently backend-authenticated
    at time.Time,
    deps previewAdmissionDependencies,
) error {
    if deps.Enrollment == nil || deps.Session == nil || deps.Replay == nil ||
        len(deps.Keys) == 0 || at.IsZero() {
        return errors.New("Wacom preview security dependencies unavailable")
    }
    if !validUUID(expected.CompanyID) || !validUUID(expected.OperatorID) ||
        !validUUID(expected.ContractID) || !validUUID(expected.SessionID) ||
        !validUUID(expected.WorkstationID) ||
        !isLowerHexSHA256(expected.ContractHash) {
        return errors.New("Wacom preview context unavailable")
    }
    enrolledID, err := deps.Enrollment.AuthenticatedWorkstationID()
    if err != nil || !validUUID(enrolledID) || enrolledID != expected.WorkstationID {
        return errors.New("Wacom workstation not authenticated or enrollment revoked")
    }
    if err := deps.Session.CheckPreviewActive(expected); err != nil {
        return fmt.Errorf("Wacom preview session unavailable: %w", err)
    }
    // Signatures and scope must pass before consuming a replay identifier.
    if err := validateAndConsumePreviewTicket(ticket, deps.Keys, expected, at, deps.Replay); err != nil {
        return err
    }
    // Reject a revocation race that occurs during ticket consumption. A
    // consumed ticket stays consumed even if this second check fails.
    if err := deps.Session.CheckPreviewActive(expected); err != nil {
        return errors.New("Wacom preview session revoked during admission")
    }
    enrolledID, err = deps.Enrollment.AuthenticatedWorkstationID()
    if err != nil || enrolledID != expected.WorkstationID {
        return errors.New("Wacom workstation enrollment changed during admission")
    }
    return nil
}
