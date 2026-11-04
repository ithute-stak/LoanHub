package main

import (
    "crypto/ed25519"
    "crypto/rand"
    "encoding/base64"
    "encoding/json"
    "errors"
    "strings"
    "testing"
    "time"
)

type fakePreviewReplay struct {
    used map[string]bool
    outage bool
}
func (f *fakePreviewReplay) ConsumeOnce(jti string, exp int64) (bool, error) {
    if f.outage { return false, errors.New("store offline") }
    if f.used[jti] { return false, nil }
    f.used[jti] = true
    return true, nil
}

func previewTestToken(t *testing.T, private ed25519.PrivateKey, now time.Time, scope previewTicketScope) string {
    t.Helper()
    header := map[string]any{"alg":"EdDSA","kid":"test-ed25519-key","typ":"WACOM-PREVIEW"}
    claims := map[string]any{
        "aud":previewTicketAudience, "purpose":previewTicketPurpose,
        "jti": strings.Repeat("z",32), "iat":now.Unix(), "exp":now.Add(30*time.Second).Unix(),
        "company_id":scope.CompanyID, "operator_id":scope.OperatorID,
        "contract_id":scope.ContractID, "contract_hash":scope.ContractHash,
        "session_id":scope.SessionID, "workstation_id":scope.WorkstationID,
    }
    enc := func(v any) string {
        b,err := json.Marshal(v)
        if err != nil { t.Fatal(err) }
        return base64.RawURLEncoding.EncodeToString(b)
    }
    input := enc(header)+"."+enc(claims)
    return input+"."+base64.RawURLEncoding.EncodeToString(ed25519.Sign(private,[]byte(input)))
}

func testPreviewScope() previewTicketScope {
    return previewTicketScope{
        CompanyID:"11111111-1111-1111-1111-111111111111",
        OperatorID:"22222222-2222-2222-2222-222222222222",
        ContractID:"33333333-3333-3333-3333-333333333333",
        ContractHash:strings.Repeat("a",64),
        SessionID:"44444444-4444-4444-4444-444444444444",
        WorkstationID:"55555555-5555-5555-5555-555555555555",
    }
}
func TestPinnedTicketVerificationAndAtomicReplayGate(t *testing.T) {
    pub,priv,err := ed25519.GenerateKey(rand.Reader)
    if err != nil { t.Fatal(err) }
    now := time.Date(2026,11,4,11,0,0,0,time.UTC)
    scope := testPreviewScope()
    token := previewTestToken(t,priv,now,scope)
    keys := map[string]ed25519.PublicKey{"test-ed25519-key":pub}
    claims,err := verifyPreviewTicketSignatureAndScope(token,keys,scope,now)
    if err != nil || claims.WorkstationID != scope.WorkstationID { t.Fatalf("verification failed: %v",err) }
    if err := validateAndConsumePreviewTicket(token,keys,scope,now,nil); err == nil {
        t.Fatal("nil replay store MUST fail closed")
    }
    store := &fakePreviewReplay{used:map[string]bool{}}
    if err := validateAndConsumePreviewTicket(token,keys,scope,now,store); err != nil { t.Fatal(err) }
    if err := validateAndConsumePreviewTicket(token,keys,scope,now,store); err == nil {
        t.Fatal("ticket replay accepted")
    }
}
func TestRejectWrongScopeSignatureExpiredOrFutureTickets(t *testing.T) {
    pub,priv,_ := ed25519.GenerateKey(rand.Reader)
    otherPub,_,_ := ed25519.GenerateKey(rand.Reader)
    now := time.Date(2026,11,4,11,0,0,0,time.UTC)
    scope := testPreviewScope()
    token := previewTestToken(t,priv,now,scope)
    keys := map[string]ed25519.PublicKey{"test-ed25519-key":pub}
    wrong := scope; wrong.WorkstationID = "77777777-7777-7777-7777-777777777777"
    for name, trial := range map[string]struct{
        ticket string; keys map[string]ed25519.PublicKey; scope previewTicketScope; clock time.Time
    }{
        "other-workstation":{token,keys,wrong,now},
        "bad-key":{token,map[string]ed25519.PublicKey{"test-ed25519-key":otherPub},scope,now},
        "expired":{token,keys,scope,now.Add(30*time.Second)},
        "not-yet-valid":{token,keys,scope,now.Add(-1*time.Second)},
        "malformed":{token+".",keys,scope,now},
    } {
        if _,err := verifyPreviewTicketSignatureAndScope(trial.ticket,trial.keys,trial.scope,trial.clock);err == nil {
            t.Errorf("%s ticket incorrectly accepted",name)
        }
    }
    chunks := strings.Split(token, ".")
    forged := chunks[0]+"."+chunks[1]+"."+base64.RawURLEncoding.EncodeToString(make([]byte,ed25519.SignatureSize))
    if _,err := verifyPreviewTicketSignatureAndScope(forged,keys,scope,now);err == nil {
        t.Fatal("forged signature accepted")
    }
}
func TestReplayStoreOutageFailsClosed(t *testing.T) {
    pub,priv,_ := ed25519.GenerateKey(rand.Reader)
    now := time.Date(2026,11,4,11,0,0,0,time.UTC)
    scope := testPreviewScope()
    token := previewTestToken(t,priv,now,scope)
    replay := &fakePreviewReplay{used:map[string]bool{},outage:true}
    if err := validateAndConsumePreviewTicket(token,map[string]ed25519.PublicKey{"test-ed25519-key":pub},scope,now,replay);err == nil {
        t.Fatal("replay-store outage allowed ticket")
    }
}
