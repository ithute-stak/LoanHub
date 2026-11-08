package main

// Fail-closed local admission policy: no third-party auth or workstation ID
// supplied by a web page. The Go process alone owns keys and bearer tokens.
import (
    "errors"
    "time"
)

type WacomLocalOperation string

const (
    WacomLookupOperation WacomLocalOperation = "lookup"
    WacomCaptureOperation WacomLocalOperation = "capture"
    WacomUploadOperation WacomLocalOperation = "upload"
    WacomDocumentEvidenceOperation WacomLocalOperation = "document_evidence"
)

func (c *LoanHubPCClient) CheckWacomLocalAuthority(op WacomLocalOperation, now time.Time) error {
    if c == nil || c.accessToken == "" || c.companyID == "" || c.operatorID == "" {
        return errors.New("LoanHub employee authentication required")
    }
    if c.workstationKeyDir == "" {
        return errors.New("Unenrolled legacy PC mode cannot perform protected operations")
    }
    if c.bridgeSessionToken == "" || !now.Before(c.bridgeSessionExpires) {
        return errors.New("Wacom workstation proof not current")
    }
    switch op {
    case WacomLookupOperation, WacomCaptureOperation,
        WacomUploadOperation, WacomDocumentEvidenceOperation:
        return nil
    default:
        return errors.New("Operation not permitted by the local Wacom workstation")
    }
}

// A local check does not replace LoanHub's per-request server authorization.
// The remote server must still validate company, employee, workstation and role.
