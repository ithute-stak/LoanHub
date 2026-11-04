package main

// Signed temporary-preview ticket verifier. This package intentionally does
// NOT register a localhost HTTP endpoint or enable handwriting transmission.
// The public key must be pinned independently of any browser-supplied request.
import (
    "crypto/ed25519"
    "crypto/subtle"
    "encoding/base64"
    "encoding/json"
    "errors"
    "fmt"
    "strings"
    "time"
)

const (
    previewTicketAudience = "loanhub-wacom-connector-preview-v1"
    previewTicketPurpose = "test-preview-only"
    maxPreviewTicketLength = 8192
)

type previewTicketHeader struct {
    Algorithm string `json:"alg"`
    KeyID string `json:"kid"`
    Type string `json:"typ"`
}
type previewTicketClaims struct {
    Audience string `json:"aud"`
    Purpose string `json:"purpose"`
    ID string `json:"jti"`
    IssuedAt int64 `json:"iat"`
    ExpiresAt int64 `json:"exp"`
    CompanyID string `json:"company_id"`
    OperatorID string `json:"operator_id"`
    ContractID string `json:"contract_id"`
    ContractHash string `json:"contract_hash"`
    SessionID string `json:"session_id"`
    WorkstationID string `json:"workstation_id"`
}

// previewTicketScope MUST be constructed from independently authenticated
// workstation/backend session state; none of its values may be taken from
// unauthenticated HTTP headers, JS messages or fields in the ticket itself.
type previewTicketScope struct {
    CompanyID string
    OperatorID string
    ContractID string
    ContractHash string
    SessionID string
    WorkstationID string
}

// This function performs signature and scope checks ONLY. It is not enough
// to authorize a request: a future production entrypoint MUST also consume
// the JTI atomically using durable replay protection and check revocation.
func verifyPreviewTicketSignatureAndScope(
    token string, pinnedKeys map[string]ed25519.PublicKey,
    expected previewTicketScope, now time.Time,
) (previewTicketClaims, error) {
    reject := func() (previewTicketClaims, error) {
        return previewTicketClaims{}, errors.New("invalid Wacom preview ticket")
    }
    if len(token) == 0 || len(token) > maxPreviewTicketLength || now.IsZero() { return reject() }
    parts := strings.Split(token, ".")
    if len(parts) != 3 { return reject() }
    decoder := base64.RawURLEncoding.Strict()
    h, err := decoder.DecodeString(parts[0]); if err != nil || len(h) > 512 { return reject() }
    p, err := decoder.DecodeString(parts[1]); if err != nil || len(p) > 4096 { return reject() }
    sig, err := decoder.DecodeString(parts[2]); if err != nil || len(sig) != ed25519.SignatureSize { return reject() }
    var header previewTicketHeader
    if err := json.Unmarshal(h, &header); err != nil { return reject() }
    if header.Algorithm != "EdDSA" || header.Type != "WACOM-PREVIEW" ||
        header.KeyID == "" || len(header.KeyID) > 64 { return reject() }
    pub, ok := pinnedKeys[header.KeyID]
    if !ok || len(pub) != ed25519.PublicKeySize { return reject() }
    if !ed25519.Verify(pub, []byte(parts[0]+"."+parts[1]), sig) { return reject() }
    var claims previewTicketClaims
    if err := json.Unmarshal(p, &claims); err != nil { return reject() }
    if claims.Audience != previewTicketAudience || claims.Purpose != previewTicketPurpose ||
        len(claims.ID) < 20 || len(claims.ID) > 128 { return reject() }
    nowSeconds := now.Unix()
    // A time window of <=60s; reject far-future tickets and any expired one.
    if claims.IssuedAt <= 0 || claims.ExpiresAt <= claims.IssuedAt ||
        claims.ExpiresAt-claims.IssuedAt > 60 ||
        claims.IssuedAt > nowSeconds || nowSeconds >= claims.ExpiresAt { return reject() }
    for _, v := range []string{expected.CompanyID, expected.OperatorID, expected.ContractID,
        expected.ContractHash, expected.SessionID, expected.WorkstationID} {
        if v == "" { return reject() }
    }
    if len(expected.ContractHash) != 64 || !isLowerHexSHA256(expected.ContractHash) { return reject() }
    for _, pair := range [][2]string{
        {claims.CompanyID, expected.CompanyID},
        {claims.OperatorID, expected.OperatorID},
        {claims.ContractID, expected.ContractID},
        {claims.ContractHash, expected.ContractHash},
        {claims.SessionID, expected.SessionID},
        {claims.WorkstationID, expected.WorkstationID},
    } {
        if subtle.ConstantTimeCompare([]byte(pair[0]), []byte(pair[1])) != 1 { return reject() }
    }
    return claims, nil
}

func isLowerHexSHA256(input string) bool {
    if len(input) != 64 { return false }
    for _, c := range input { if !((c >= '0' && c <= '9') || (c >= 'a' && c <= 'f')) { return false } }
    return true
}

// previewTicketReplayStore is a required *durable* atomic consume interface;
// e.g. Redis SET NX with a TTL expiring after the token. Nil must fail closed.
// No in-process map is acceptable for production replay prevention.
type previewTicketReplayStore interface {
    ConsumeOnce(jti string, expiresAt int64) (bool, error)
}

// validateAndConsumePreviewTicket is deliberately not wired to an HTTP route.
// Revocation and enrolled-device checks are still required by future callers.
func validateAndConsumePreviewTicket(
    token string, pinnedKeys map[string]ed25519.PublicKey,
    expected previewTicketScope, now time.Time, replay previewTicketReplayStore,
) error {
    if replay == nil { return errors.New("durable Wacom preview replay protection not configured") }
    claims, err := verifyPreviewTicketSignatureAndScope(token, pinnedKeys, expected, now)
    if err != nil { return err }
    accepted, err := replay.ConsumeOnce(claims.ID, claims.ExpiresAt)
    if err != nil { return fmt.Errorf("Wacom replay protection unavailable: %w", err) }
    if !accepted { return errors.New("Wacom preview ticket already used") }
    return nil
}
