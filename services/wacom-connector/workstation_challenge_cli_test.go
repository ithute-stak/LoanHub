package main

import (
  "crypto/ed25519"
  "encoding/base64"
  "encoding/json"
  "os"
  "path/filepath"
  "strings"
  "testing"
  "time"
)

func TestManualWorkstationChallengeResponseWithPersistentIdentity(t *testing.T) {
  dir:=filepath.Join(t.TempDir(),"private")
  if err:=os.Mkdir(dir,0700);err!=nil {t.Fatal(err)}
  public,err:=initializeWorkstationIdentity(dir)
  if err!=nil {t.Fatal(err)}
  _,private,err:=loadWorkstationIdentity(dir)
  if err!=nil {t.Fatal(err)}
  now:=time.Date(2026,11,4,15,0,0,0,time.UTC)
  challenge:=workstationChallengeEnvelope{
    ChallengeID:"11111111-1111-4111-8111-111111111111",
    WorkstationID:public.WorkstationID,
    SessionID:"22222222-2222-4222-8222-222222222222",
    Nonce:base64.RawURLEncoding.EncodeToString([]byte(strings.Repeat("x",32))),
    IssuedAt:now.Format(time.RFC3339Nano),
    ExpiresAt:now.Add(30*time.Second).Format(time.RFC3339Nano),
    CaptureEnabled:false,
  }
  raw,err:=json.Marshal(challenge)
  if err!=nil {t.Fatal(err)}
  result,err:=signBackendWorkstationChallenge(dir,strings.NewReader(string(raw)),now.Add(time.Second))
  if err!=nil {t.Fatal(err)}
  if result.ChallengeID!=challenge.ChallengeID||result.WorkstationID!=public.WorkstationID {
    t.Fatal("wrong challenge response scope")
  }
  signature,err:=base64.StdEncoding.DecodeString(result.SignatureBase64)
  if err!=nil {t.Fatal(err)}
  message,err:=workstationProofMessage(workstationProofChallenge{
    WorkstationID:challenge.WorkstationID,SessionID:challenge.SessionID,
    Nonce:challenge.Nonce,IssuedAt:now,ExpiresAt:now.Add(30*time.Second),
  },now.Add(time.Second))
  if err!=nil {t.Fatal(err)}
  if !ed25519.Verify(private.Public().(ed25519.PublicKey),message,signature) {
    t.Fatal("proof does not verify with enrolled public key")
  }
}
func TestManualChallengeRejectsWrongWorkstationExpiredAndNoncanonicalInputs(t *testing.T) {
  dir:=filepath.Join(t.TempDir(),"private")
  if err:=os.Mkdir(dir,0700);err!=nil {t.Fatal(err)}
  public,err:=initializeWorkstationIdentity(dir)
  if err!=nil {t.Fatal(err)}
  now:=time.Date(2026,11,4,15,0,0,0,time.UTC)
  valid:=workstationChallengeEnvelope{
    ChallengeID:"11111111-1111-4111-8111-111111111111",
    WorkstationID:public.WorkstationID,
    SessionID:"22222222-2222-4222-8222-222222222222",
    Nonce:base64.RawURLEncoding.EncodeToString([]byte(strings.Repeat("x",32))),
    IssuedAt:now.Format(time.RFC3339Nano),
    ExpiresAt:now.Add(30*time.Second).Format(time.RFC3339Nano),
  }
  checks:=[]struct{name string;change func(*workstationChallengeEnvelope);time time.Time}{
    {"wrong workstation",func(x *workstationChallengeEnvelope){x.WorkstationID="33333333-3333-4333-8333-333333333333"},now},
    {"expired",func(x *workstationChallengeEnvelope){},now.Add(30*time.Second)},
    {"capture requested",func(x *workstationChallengeEnvelope){x.CaptureEnabled=true},now},
    {"invalid nonce",func(x *workstationChallengeEnvelope){x.Nonce="invalid"},now},
    {"too long",func(x *workstationChallengeEnvelope){x.ExpiresAt=now.Add(31*time.Second).Format(time.RFC3339Nano)},now},
  }
  for _,c:=range checks {
    item:=valid;c.change(&item)
    raw,err:=json.Marshal(item);if err!=nil {t.Fatal(err)}
    if _,err:=signBackendWorkstationChallenge(dir,strings.NewReader(string(raw)),c.time);err==nil{
      t.Errorf("%s incorrectly signed",c.name)
    }
  }
  raw,_:=json.Marshal(valid)
  if _,err:=signBackendWorkstationChallenge(dir,strings.NewReader(string(raw)+" {}"),now);err==nil {
    t.Fatal("multiple challenge objects accepted")
  }
  if _,err:=signBackendWorkstationChallenge(dir,strings.NewReader(string(raw)+" "+strings.Repeat(" ",3000)),now);err==nil {
    t.Fatal("oversized challenge input accepted")
  }
}
