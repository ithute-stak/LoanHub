package main

import (
 "bytes"
 "crypto/ed25519"
 "crypto/rand"
 "encoding/base64"
 "encoding/json"
 "fmt"
 "net/http"
 "net/http/httptest"
 "os"
 "path/filepath"
 "testing"
 "time"
)

func TestLocalWorkstationProofHandlerRequiresSignedBackendChallengeAndTrustedOrigin(t *testing.T){
 dir:=filepath.Join(t.TempDir(),"identity")
 if err:=os.Mkdir(dir,0700);err!=nil{t.Fatal(err)}
 identity,err:=initializeWorkstationIdentity(dir)
 if err!=nil{t.Fatal(err)}
 backendPublic,backendPrivate,err:=ed25519.GenerateKey(rand.Reader)
 if err!=nil{t.Fatal(err)}
 now:=time.Now().UTC()
 expires:=now.Add(20*time.Second)
 ch:=backendWorkstationChallenge{
  ChallengeID:"22222222-2222-4222-8222-222222222222",
  WorkstationID:identity.WorkstationID,
  SessionID:"11111111-1111-4111-8111-111111111111",
  Nonce:base64.RawURLEncoding.EncodeToString(bytes.Repeat([]byte{0x35},32)),
  IssuedAt:now.Format(time.RFC3339Nano),
  ExpiresAt:expires.Format(time.RFC3339Nano),
  BackendSigningKID:"trusted-backend",
 }
 message:=[]byte(fmt.Sprintf("LOANHUB-WACOM-CHALLENGE-ENVELOPE-V1\n%s\n%s\n%s\n%s\n%d\n",
  ch.ChallengeID,ch.WorkstationID,ch.SessionID,ch.Nonce,expires.Unix()))
 ch.BackendSignatureBase64=base64.StdEncoding.EncodeToString(ed25519.Sign(backendPrivate,message))
 h:=&localWacomChallengeProofHandler{
  IdentityDirectory:dir,
  TrustedBackendKeys:map[string]ed25519.PublicKey{"trusted-backend":backendPublic},
 }
 call:=func(challenge backendWorkstationChallenge,origin string)*httptest.ResponseRecorder {
  raw,_:=json.Marshal(challenge)
  req:=httptest.NewRequest("POST","http://127.0.0.1:8765"+localWacomChallengeProofPath,bytes.NewReader(raw))
  req.Header.Set("Origin",origin)
  req.Header.Set("Content-Type","application/json")
  w:=httptest.NewRecorder()
  h.ServeHTTP(w,req)
  return w
 }
 ok:=call(ch,"https://loanhub.co.ls")
 if ok.Code!=http.StatusOK {t.Fatalf("signed backend challenge rejected: %d %s",ok.Code,ok.Body.String())}
 var proof workstationProofSubmission
 if err:=json.Unmarshal(ok.Body.Bytes(),&proof);err!=nil{t.Fatal(err)}
 if proof.ChallengeID!=ch.ChallengeID{t.Fatal("wrong proof challenge returned")}
 ch.BackendSigningKID="other-backend"
 if denied:=call(ch,"https://loanhub.co.ls");denied.Code==http.StatusOK{t.Fatal("untrusted issuer key accepted")}
 // Origin is checked before the signer or challenge.
 if denied:=call(ch,"https://evil.example");denied.Code!=http.StatusForbidden{t.Fatal("foreign browser origin accepted")}
}
