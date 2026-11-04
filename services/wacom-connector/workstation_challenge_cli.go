package main

// Operator-invoked response to a backend-generated challenge. This does not
// request a challenge, contact the backend, register a key, or sign a contract.
// A human operator must independently obtain the challenge through the
// authenticated LoanHub API. Never accept a web-browser request to sign.
import (
    "bytes"
    "encoding/base64"
    "encoding/json"
    "errors"
    "io"
    "time"
)

const maxWorkstationChallengeJSON = 2048

type workstationChallengeEnvelope struct {
    ChallengeID string `json:"challenge_id"`
    WorkstationID string `json:"workstation_id"`
    SessionID string `json:"session_id"`
    Nonce string `json:"nonce"`
    IssuedAt string `json:"issued_at"`
    ExpiresAt string `json:"expires_at"`
    CaptureEnabled bool `json:"capture_enabled"`
}
type workstationProofEnvelope struct {
    ChallengeID string `json:"challenge_id"`
    WorkstationID string `json:"workstation_id"`
    SignatureBase64 string `json:"signature_base64"`
}

func signBackendWorkstationChallenge(directory string, input io.Reader, now time.Time) (workstationProofEnvelope,error) {
    reject:=func() (workstationProofEnvelope,error) {return workstationProofEnvelope{},errors.New("invalid, mismatched or expired Wacom workstation challenge")}
    if input == nil || now.IsZero() {return reject()}
    // Strict, one-object input. Never read an unbounded challenge payload.
    raw, readErr := io.ReadAll(io.LimitReader(input,maxWorkstationChallengeJSON+1))
    if readErr != nil || len(raw) > maxWorkstationChallengeJSON {return reject()}
    dec:=json.NewDecoder(bytes.NewReader(raw))
    dec.DisallowUnknownFields()
    var envelope workstationChallengeEnvelope
    if err:=dec.Decode(&envelope);err!=nil {return reject()}
    if err:=dec.Decode(new(any));err!=io.EOF {return reject()}
    if !validUUID(envelope.ChallengeID) || !validUUID(envelope.WorkstationID) ||
        !validUUID(envelope.SessionID) || envelope.CaptureEnabled {
        return reject()
    }
    issued,err:=time.Parse(time.RFC3339Nano,envelope.IssuedAt)
    if err!=nil {return reject()}
    expires,err:=time.Parse(time.RFC3339Nano,envelope.ExpiresAt)
    if err!=nil {return reject()}
    localID,private,err:=loadWorkstationIdentity(directory)
    if err!=nil {return workstationProofEnvelope{},err}
    if localID!=envelope.WorkstationID {return reject()}
    challenge:=workstationProofChallenge{
        WorkstationID:localID,SessionID:envelope.SessionID,Nonce:envelope.Nonce,
        IssuedAt:issued,ExpiresAt:expires,
    }
    signed,err:=signWorkstationProof(challenge,now,private)
    if err!=nil {return reject()}
    return workstationProofEnvelope{
        ChallengeID:envelope.ChallengeID,
        WorkstationID:localID,
        SignatureBase64:base64.StdEncoding.EncodeToString(signed),
    },nil
}
