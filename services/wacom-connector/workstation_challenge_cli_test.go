package main

import (
 "bytes"
 "crypto/ed25519"
 "crypto/rand"
 "fmt"
 "encoding/base64"
 "encoding/json"
 "os"
 "path/filepath"
 "strings"
 "testing"
 "time"
)

func TestLocalBackendChallengeSignsOnlyBoundEnrolledSession(t *testing.T){
 dir:=filepath.Join(t.TempDir(),"identity")
 if err:=os.Mkdir(dir,0700);err!=nil{t.Fatal(err)}
 identity,err:=initializeWorkstationIdentity(dir)
 if err!=nil{t.Fatal(err)}
 now:=time.Now().UTC().Truncate(time.Second)
 session:="11111111-1111-4111-8111-111111111111"
 challenge:=backendWorkstationChallenge{
  ChallengeID:"22222222-2222-4222-8222-222222222222",
  WorkstationID:identity.WorkstationID,SessionID:session,
  Nonce:base64.RawURLEncoding.EncodeToString(bytes.Repeat([]byte{0x35},32)),
  IssuedAt:now.Add(-time.Second).Format(time.RFC3339Nano),
  ExpiresAt:now.Add(20*time.Second).Format(time.RFC3339Nano),
  CaptureEnabled:false,
 }
 backendPublic,backendPrivate,err:=ed25519.GenerateKey(rand.Reader)
 if err!=nil{t.Fatal(err)}
 challenge.BackendSigningKID="verified-test-backend"
 challenge.BackendSignatureBase64=base64.StdEncoding.EncodeToString(ed25519.Sign(backendPrivate,
  []byte(fmt.Sprintf("LOANHUB-WACOM-CHALLENGE-ENVELOPE-V1\n%s\n%s\n%s\n%s\n%d\n",
   challenge.ChallengeID,challenge.WorkstationID,challenge.SessionID,challenge.Nonce,now.Add(20*time.Second).Unix()))))
 keys:=map[string]ed25519.PublicKey{challenge.BackendSigningKID:backendPublic}
 input,_:=json.Marshal(challenge)
 proof,err:=signBackendWacomChallenge(dir,session,bytes.NewReader(input),now,keys)
 if err!=nil{t.Fatal(err)}
 pub,err:=base64.StdEncoding.DecodeString(identity.PublicKeyBase64)
 if err!=nil{t.Fatal(err)}
 sig,err:=base64.StdEncoding.DecodeString(proof.SignatureBase64)
 if err!=nil{t.Fatal(err)}
 message,err:=workstationProofMessage(workstationProofChallenge{
  WorkstationID:identity.WorkstationID,SessionID:session,
  Nonce:challenge.Nonce,
  IssuedAt:now.Add(-time.Second),ExpiresAt:now.Add(20*time.Second),
 },now)
 if err!=nil{t.Fatal(err)}
 if !ed25519.Verify(pub,message,sig) {t.Fatal("backend would reject local workstation proof")}
 if proof.ChallengeID!=challenge.ChallengeID ||proof.WorkstationID!=identity.WorkstationID {t.Fatal("wrong proof binding")}
 challenge.WorkstationID="33333333-3333-4333-8333-333333333333"
 bad,_:=json.Marshal(challenge)
 if _,err:=signBackendWacomChallenge(dir,session,bytes.NewReader(bad),now,keys);err==nil{t.Fatal("foreign workstation accepted")}
 challenge.WorkstationID=identity.WorkstationID
 if _,err:=signBackendWacomChallenge(dir,"44444444-4444-4444-8444-444444444444",bytes.NewReader(input),now,keys);err==nil{t.Fatal("wrong session accepted")}
 challenge.ExpiresAt=now.Add(-time.Second).Format(time.RFC3339Nano)
 bad,_=json.Marshal(challenge)
 if _,err:=signBackendWacomChallenge(dir,session,bytes.NewReader(bad),now,keys);err==nil{t.Fatal("expired challenge accepted")}
}
func TestLocalBackendChallengeRejectsUntrustedInputs(t *testing.T){
 dir:=filepath.Join(t.TempDir(),"identity")
 if err:=os.Mkdir(dir,0700);err!=nil{t.Fatal(err)}
 _,err:=initializeWorkstationIdentity(dir)
 if err!=nil{t.Fatal(err)}
 session:="11111111-1111-4111-8111-111111111111"
 for _,input:=range []string{"", "{}",strings.Repeat("a",maxWacomChallengeJSON+1),"{\"challenge_id\":\"x\",\"extra\":true}","{} {}"}{
  if _,err:=signBackendWacomChallenge(dir,session,strings.NewReader(input),time.Now().UTC(),map[string]ed25519.PublicKey{"test":make([]byte,32)});err==nil{t.Fatalf("accepted unsafe input %q",input[:min(len(input),40)])}
 }
}
