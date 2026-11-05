package main

// Local-only helper to sign a backend-issued workstation challenge.
// There is deliberately no HTTP endpoint: the enrolled private key is
// never served to a browser, an operator API or an external caller.
import (
 "bytes"
 "crypto/ed25519"
 "fmt"
 "encoding/base64"
 "encoding/json"
 "errors"
 "io"
 "strings"
 "time"
)

const maxWacomChallengeJSON = 2048

type backendWorkstationChallenge struct {
 ChallengeID string `json:"challenge_id"`
 WorkstationID string `json:"workstation_id"`
 SessionID string `json:"session_id"`
 Nonce string `json:"nonce"`
 IssuedAt string `json:"issued_at"`
 ExpiresAt string `json:"expires_at"`
 CaptureEnabled bool `json:"capture_enabled"`
 BackendSignatureBase64 string `json:"backend_signature_base64"`
 BackendSigningKID string `json:"backend_signing_kid"`
}
type workstationProofSubmission struct {
 ChallengeID string `json:"challenge_id"`
 WorkstationID string `json:"workstation_id"`
 SignatureBase64 string `json:"signature_base64"`
}

// signBackendWacomChallenge requires the expected session ID to be
// independently selected by the operator. A supplied challenge cannot
// silently switch the session or workstation. This signature is proof of
// enrollment, not a preview authorization or consent.
func signBackendWacomChallenge(directory, expectedSessionID string, input io.Reader, now time.Time, trustedBackendKeys map[string]ed25519.PublicKey)(
 workstationProofSubmission,error,
){
 denied:=errors.New("Wacom workstation challenge signing unavailable")
 if input==nil||!validUUID(expectedSessionID)||now.IsZero()||len(trustedBackendKeys)==0{return workstationProofSubmission{},denied}
 raw,err:=io.ReadAll(io.LimitReader(input,maxWacomChallengeJSON+1))
 if err!=nil||len(raw)==0||len(raw)>maxWacomChallengeJSON{return workstationProofSubmission{},denied}
 decoder:=json.NewDecoder(bytes.NewReader(raw))
 decoder.DisallowUnknownFields()
 var challenge backendWorkstationChallenge
 if err=decoder.Decode(&challenge);err!=nil{return workstationProofSubmission{},denied}
 var tail any
 if err=decoder.Decode(&tail);err!=io.EOF{return workstationProofSubmission{},denied}
 workstationID,private,err:=loadWorkstationIdentity(directory)
 if err!=nil{return workstationProofSubmission{},denied}
 defer func(){for i:=range private {private[i]=0}}()
 if !validUUID(challenge.ChallengeID)||challenge.WorkstationID!=workstationID||
  challenge.SessionID!=expectedSessionID||challenge.CaptureEnabled||
  strings.TrimSpace(challenge.IssuedAt)==""||strings.TrimSpace(challenge.ExpiresAt)==""{
  return workstationProofSubmission{},denied
 }
 issued,err:=time.Parse(time.RFC3339Nano,challenge.IssuedAt)
 if err!=nil{return workstationProofSubmission{},denied}
 expires,err:=time.Parse(time.RFC3339Nano,challenge.ExpiresAt)
 if err!=nil{return workstationProofSubmission{},denied}
 // Verify a dedicated backend signature before allowing private-key use.
 // The challenge is NOT trusted merely because a browser supplied it.
 backendKey,ok:=trustedBackendKeys[challenge.BackendSigningKID]
 if !ok||len(backendKey)!=ed25519.PublicKeySize{return workstationProofSubmission{},denied}
 backendSignature,err:=base64.StdEncoding.Strict().DecodeString(challenge.BackendSignatureBase64)
 if err!=nil||len(backendSignature)!=ed25519.SignatureSize{return workstationProofSubmission{},denied}
 envelope:=[]byte(fmt.Sprintf("LOANHUB-WACOM-CHALLENGE-ENVELOPE-V1\n%s\n%s\n%s\n%s\n%d\n",
  challenge.ChallengeID,challenge.WorkstationID,challenge.SessionID,
  challenge.Nonce,expires.Unix()))
 if !ed25519.Verify(backendKey,envelope,backendSignature){return workstationProofSubmission{},denied}
 signature,err:=signWorkstationProof(workstationProofChallenge{
  WorkstationID:workstationID,SessionID:expectedSessionID,
  Nonce:challenge.Nonce,IssuedAt:issued,ExpiresAt:expires,
 },now,private)
 if err!=nil{return workstationProofSubmission{},denied}
 return workstationProofSubmission{
  ChallengeID:challenge.ChallengeID,
  WorkstationID:workstationID,
  SignatureBase64:base64.StdEncoding.EncodeToString(signature),
 },nil
}
