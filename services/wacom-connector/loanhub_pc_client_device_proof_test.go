package main

import (
    "context"
    "crypto/ed25519"
    "encoding/base64"
    "encoding/json"
    "fmt"
    "net/http"
    "os"
    "path/filepath"
    "testing"
    "time"
)

// Exercise the complete HTTPS challenge exchange with a disposable Ed25519
// identity. Neither private key nor LoanHub password is sent to the server.
func TestLoanHubPCFirstPartyDeviceProof(t *testing.T) {
    dir := filepath.Join(t.TempDir(), "pc-identity")
    if err := os.Mkdir(dir, 0700); err != nil { t.Fatal(err) }
    identity, err := initializeWorkstationIdentity(dir)
    if err != nil { t.Fatal(err) }
    publicKey, err := base64.StdEncoding.DecodeString(identity.PublicKeyBase64)
    if err != nil { t.Fatal(err) }
    company := "22345678-1234-4234-8234-123456789012"
    employee := "32345678-1234-4234-8234-123456789012"
    challengeID := "42345678-1234-4234-8234-123456789012"
    nonce := base64.RawURLEncoding.EncodeToString([]byte("01234567890123456789012345678901"))
    expiry := time.Now().Add(25*time.Second).UTC().Truncate(time.Second)
    proofCount := 0
    client,server := newTestLoanHubPC(t,func(w http.ResponseWriter,r *http.Request) {
        w.Header().Set("Content-Type","application/json")
        if r.URL.Path != "/api/v1/auth/login" &&
            (r.Header.Get("X-Company-ID")!=company || r.Header.Get("Authorization")!="Bearer synthetic") {
            t.Fatal("Missing authenticated company context")
        }
        switch r.URL.Path {
        case "/api/v1/auth/login":
            _=json.NewEncoder(w).Encode(map[string]any{
                "access_token":"synthetic","token_type":"bearer",
                "user":map[string]any{"id":employee,"is_active":true,
                    "memberships":[]any{map[string]any{"company_id":company,"is_active":true}}},
            })
        case "/api/v1/contract-signing/workstations/"+identity.WorkstationID+"/my-assignment":
            _=json.NewEncoder(w).Encode(map[string]any{
                "assigned":true,"operator_id":employee,"workstation_id":identity.WorkstationID,
                "bridge_session_authorized":false,"signing_authorized":false,"device_proof_required":true,
            })
        case "/api/v1/wacom-bridge/device-challenges":
            _=json.NewEncoder(w).Encode(map[string]any{
                "challenge_id":challengeID,"company_id":company,"employee_user_id":employee,
                "workstation_id":identity.WorkstationID,"nonce":nonce,
                "expires_at":expiry.Format(time.RFC3339),
                "device_proof_required":true,"signing_authorized":false,
            })
        case "/api/v1/wacom-bridge/device-proofs":
            proofCount++
            var data struct{
                ChallengeID string `json:"challenge_id"`
                WorkstationID string `json:"workstation_id"`
                SignatureBase64 string `json:"signature_base64"`
            }
            if err:=json.NewDecoder(r.Body).Decode(&data);err!=nil{t.Fatal(err)}
            if data.ChallengeID!=challengeID||data.WorkstationID!=identity.WorkstationID {
                t.Fatal("Incorrect proof scope")
            }
            signature,err:=base64.StdEncoding.DecodeString(data.SignatureBase64)
            if err!=nil{t.Fatal(err)}
            message:=[]byte("LOANHUB-WACOM-BRIDGE-DEVICE-V1\n"+company+"\n"+employee+"\n"+
                identity.WorkstationID+"\n"+challengeID+"\n"+nonce+"\n"+
                fmt.Sprintf("%d\n",expiry.Unix()))
            if !ed25519.Verify(ed25519.PublicKey(publicKey),message,signature) {
                t.Fatal("Ed25519 proof not valid for backend challenge")
            }
            _=json.NewEncoder(w).Encode(map[string]any{
                "device_proof_verified":true,"employee_user_id":employee,
                "workstation_id":identity.WorkstationID,"bridge_session_authorized":false,
                "capture_authorized":false,"contract_signed":false,
            })
        default:
            t.Fatalf("Unexpected endpoint %s",r.URL.Path)
        }
    })
    defer server.Close()
    if err:=client.Login(context.Background(),"59000000","synthetic-password","","");err!=nil { t.Fatal(err) }
    if err:=client.VerifyLocalWorkstation(context.Background(),dir);err!=nil { t.Fatal(err) }
    if proofCount!=1 { t.Fatalf("Expected exactly one proof, got %d",proofCount) }
    client.Logout()
    if err:=client.VerifyLocalWorkstation(context.Background(),dir);err==nil {
        t.Fatal("Logged-out operator could prove device")
    }
}

func TestLoanHubPCProofFailsClosedOnWrongScope(t *testing.T) {
    dir:=filepath.Join(t.TempDir(),"pc-identity")
    if err:=os.Mkdir(dir,0700);err!=nil{t.Fatal(err)}
    identity,err:=initializeWorkstationIdentity(dir)
    if err!=nil{t.Fatal(err)}
    company:="22345678-1234-4234-8234-123456789012"
    employee:="32345678-1234-4234-8234-123456789012"
    requests:=0
    client,server:=newTestLoanHubPC(t,func(w http.ResponseWriter,r *http.Request) {
        requests++
        w.Header().Set("Content-Type","application/json")
        switch r.URL.Path {
        case "/api/v1/contract-signing/workstations/"+identity.WorkstationID+"/my-assignment":
            _=json.NewEncoder(w).Encode(map[string]any{
                "assigned":true,"operator_id":employee,"workstation_id":identity.WorkstationID,
                "device_proof_required":true,"bridge_session_authorized":false,"signing_authorized":false,
            })
        case "/api/v1/wacom-bridge/device-challenges":
            _=json.NewEncoder(w).Encode(map[string]any{
                "challenge_id":"42345678-1234-4234-8234-123456789012",
                "company_id":company,"employee_user_id":"an-attacker",
                "workstation_id":identity.WorkstationID,
                "nonce":base64.RawURLEncoding.EncodeToString([]byte("01234567890123456789012345678901")),
                "expires_at":time.Now().Add(20*time.Second).UTC().Format(time.RFC3339),
                "device_proof_required":true,"signing_authorized":false,
            })
        case "/api/v1/wacom-bridge/device-proofs":
            t.Fatal("Must not sign or submit a mismatched server challenge")
        default:
            t.Fatal("Unexpected request")
        }
    })
    defer server.Close()
    client.accessToken="synthetic"; client.companyID=company; client.operatorID=employee
    if err:=client.VerifyLocalWorkstation(context.Background(),dir);err==nil {
        t.Fatal("Accepted a challenge for the wrong employee")
    }
    if requests!=2 {t.Fatalf("Expected assignment and challenge only, got %d",requests)}
}
