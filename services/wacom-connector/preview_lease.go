package main

import (
    "crypto/rand"
    "crypto/subtle"
    "encoding/base64"
    "errors"
    "regexp"
    "sync"
    "time"
)

// Local preview admission policy: no network listener or signature exposure.
// This deliberately cannot sign contracts, save evidence, or authenticate
// a borrower. Only a future backend-issued, authenticated ticket may authorize
// a real capture stream. A local lease is NOT such a ticket.
var lowercaseSHA256 = regexp.MustCompile(`^[0-9a-f]{64}$`)

type previewScope struct {
    CompanyID string
    BorrowerID string
    ContractID string
    SessionID string
    ContractSHA256 string
}

// localPreviewLease is a single-use, locally held guard for development
// previews. No raw handwriting data or reusable borrower signature is stored.
type localPreviewLease struct {
    mu sync.Mutex
    scope previewScope
    token string
    expires time.Time
    consumed bool
    revoked bool
}

func validPreviewScope(scope previewScope) bool {
    return validUUID(scope.CompanyID) && validUUID(scope.BorrowerID) &&
        validUUID(scope.ContractID) && validUUID(scope.SessionID) &&
        lowercaseSHA256.MatchString(scope.ContractSHA256)
}

var canonicalUUID = regexp.MustCompile(`^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$`)

func validUUID(value string) bool { return canonicalUUID.MatchString(value) }

// createLocalPreviewLease is a fail-closed primitive for a future authenticated
// workflow. Do not call this on the strength of a browser POST alone.
func createLocalPreviewLease(scope previewScope, lifetime time.Duration, now time.Time) (*localPreviewLease, string, error) {
    if !validPreviewScope(scope) || lifetime <= 0 || lifetime > 2*time.Minute || now.IsZero() {
        return nil, "", errors.New("invalid preview scope or lease duration")
    }
    bytes := make([]byte, 32)
    if _, err := rand.Read(bytes); err != nil { return nil, "", err }
    token := base64.RawURLEncoding.EncodeToString(bytes)
    return &localPreviewLease{scope: scope, token: token, expires: now.Add(lifetime)}, token, nil
}

// consume admits a single ephemeral preview use, binding the same immutable
// company, borrower, contract, session and document digest. Caller is
// responsible for *independent* workstation/backend identity verification.
func (lease *localPreviewLease) consume(scope previewScope, token string, now time.Time) error {
    if lease == nil { return errors.New("preview lease missing") }
    lease.mu.Lock()
    defer lease.mu.Unlock()
    if lease.consumed || lease.revoked || now.IsZero() || !now.Before(lease.expires) ||
        !validPreviewScope(scope) || scope != lease.scope ||
        subtle.ConstantTimeCompare([]byte(lease.token), []byte(token)) != 1 {
        return errors.New("preview not authorized")
    }
    lease.consumed = true
    return nil
}

func (lease *localPreviewLease) revoke() {
    if lease == nil { return }
    lease.mu.Lock()
    defer lease.mu.Unlock()
    lease.revoked = true
    lease.token = ""
}
