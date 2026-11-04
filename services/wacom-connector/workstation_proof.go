package main

// Produce a signed response to a backend-generated workstation challenge.
// This intentionally has no HTTP route and accepts only a caller-supplied
// Ed25519 private key from a future protected workstation enrollment store.
// It MUST NOT trust a browser-supplied challenge or authorize signing itself.
import (
    "crypto/ed25519"
    "encoding/base64"
    "errors"
    "fmt"
    "regexp"
    "time"
)

var workstationProofNonce = regexp.MustCompile(`^[A-Za-z0-9_-]{43}$`)
const workstationProofPrefix = "LOANHUB-WACOM-WORKSTATION-POP-V1"

type workstationProofChallenge struct {
    WorkstationID string
    SessionID string
    Nonce string
    IssuedAt time.Time
    ExpiresAt time.Time
}

func workstationProofMessage(c workstationProofChallenge, now time.Time) ([]byte, error) {
    if !validUUID(c.WorkstationID) || !validUUID(c.SessionID) ||
        !workstationProofNonce.MatchString(c.Nonce) {
        return nil, errors.New("invalid workstation proof context")
    }
    decoded, err := base64.RawURLEncoding.Strict().DecodeString(c.Nonce)
    if err != nil || len(decoded) != 32 { return nil, errors.New("invalid proof nonce") }
    if c.IssuedAt.IsZero() || c.ExpiresAt.IsZero() || now.IsZero() ||
        !c.ExpiresAt.After(c.IssuedAt) || c.ExpiresAt.Sub(c.IssuedAt) > 30*time.Second ||
        now.Before(c.IssuedAt) || !now.Before(c.ExpiresAt) {
        return nil, errors.New("workstation challenge has expired")
    }
    return []byte(fmt.Sprintf("%s\n%s\n%s\n%s\n%d\n",
        workstationProofPrefix, c.WorkstationID, c.SessionID,
        c.Nonce, c.ExpiresAt.Unix())), nil
}

func signWorkstationProof(c workstationProofChallenge, now time.Time,
    private ed25519.PrivateKey) ([]byte, error) {
    if len(private) != ed25519.PrivateKeySize {
        return nil, errors.New("workstation signing key unavailable")
    }
    message, err := workstationProofMessage(c, now)
    if err != nil { return nil, err }
    return ed25519.Sign(private, message), nil
}
