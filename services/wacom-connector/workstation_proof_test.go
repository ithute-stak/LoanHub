package main

import (
    "crypto/ed25519"
    "crypto/rand"
    "encoding/base64"
    "strings"
    "testing"
    "time"
)

func TestWorkstationProofSignatureMatchesBoundedCanonicalChallenge(t *testing.T) {
    pub,priv,err:=ed25519.GenerateKey(rand.Reader)
    if err!=nil {t.Fatal(err)}
    now:=time.Date(2026,11,4,12,0,0,0,time.UTC)
    challenge:=workstationProofChallenge{
        WorkstationID:"11111111-1111-1111-1111-111111111111",
        SessionID:"22222222-2222-2222-2222-222222222222",
        Nonce:base64.RawURLEncoding.EncodeToString([]byte(strings.Repeat("x",32))),
        IssuedAt:now, ExpiresAt:now.Add(20*time.Second),
    }
    message,err:=workstationProofMessage(challenge,now.Add(time.Second))
    if err!=nil {t.Fatal(err)}
    expected:="LOANHUB-WACOM-WORKSTATION-POP-V1\n"+
        challenge.WorkstationID+"\n"+challenge.SessionID+"\n"+
        challenge.Nonce+"\n"+ "1793793620\n"
    if string(message)!=expected {t.Fatalf("canonical bytes mismatch: %q != %q",message,expected)}
    signature,err:=signWorkstationProof(challenge,now.Add(time.Second),priv)
    if err!=nil || !ed25519.Verify(pub,message,signature) {t.Fatalf("proof signature invalid: %v",err)}
}
func TestWorkstationProofCannotSignWrongSessionOrExpiredChallenge(t *testing.T) {
    _,priv,_:=ed25519.GenerateKey(rand.Reader)
    now:=time.Date(2026,11,4,12,0,0,0,time.UTC)
    challenge:=workstationProofChallenge{
        WorkstationID:"11111111-1111-1111-1111-111111111111",
        SessionID:"22222222-2222-2222-2222-222222222222",
        Nonce:base64.RawURLEncoding.EncodeToString([]byte(strings.Repeat("x",32))),
        IssuedAt:now, ExpiresAt:now.Add(20*time.Second),
    }
    if _,err:=signWorkstationProof(challenge,now.Add(20*time.Second),priv);err==nil {
        t.Fatal("expired proof accepted")
    }
    challenge.SessionID="not-an-uuid"
    if _,err:=signWorkstationProof(challenge,now.Add(time.Second),priv);err==nil {
        t.Fatal("invalid scoped session accepted")
    }
    challenge.SessionID="22222222-2222-2222-2222-222222222222"
    challenge.Nonce="invalid"
    if _,err:=signWorkstationProof(challenge,now.Add(time.Second),priv);err==nil {
        t.Fatal("invalid nonce accepted")
    }
}
