package main

import (
    "context"
    "encoding/json"
    "net/http"
    "testing"
    "time"
)

func TestLoanHubWacomRevocationDeletesLocalCredentialOnlyAfterServerAcknowledges(t *testing.T) {
    token := "wb1_abcdefghijklmnopqrstuvwxyz0123456789ABCDE12"
    calls := 0
    client,server := newTestLoanHubPC(t,func(w http.ResponseWriter,r *http.Request) {
        calls++
        if r.Method!=http.MethodPost || r.URL.Path!="/api/v1/wacom-bridge/sessions/revoke" ||
            r.Header.Get("Authorization")!="Bearer synthetic" ||
            r.Header.Get("X-Company-ID")!="company" ||
            r.Header.Get("X-Wacom-Bridge-Session")!=token {
            t.Fatal("Wrong revocation authentication")
        }
        w.Header().Set("Content-Type","application/json")
        _=json.NewEncoder(w).Encode(map[string]any{"revoked":true,"signing_authorized":false})
    })
    defer server.Close()
    client.accessToken="synthetic"
    client.companyID="company"
    client.bridgeSessionToken=token
    client.bridgeSessionExpires=time.Now().Add(time.Minute)
    if err:=client.RevokeBridgeSession(context.Background());err!=nil{t.Fatal(err)}
    if calls!=1 || client.bridgeSessionToken!="" || !client.bridgeSessionExpires.IsZero(){
        t.Fatal("Failed to revoke and clear Wacom capability")
    }
    if err:=client.RevokeBridgeSession(context.Background());err!=nil{t.Fatal(err)}
    if calls!=1 {t.Fatal("Sent redundant revocation without credential")}
}

func TestLoanHubWacomRevocationFailsClosedOnRejectedResponse(t *testing.T) {
    client,server := newTestLoanHubPC(t,func(w http.ResponseWriter,r *http.Request) {
        http.Error(w,"Denied",http.StatusForbidden)
    })
    defer server.Close()
    client.accessToken="synthetic"
    client.companyID="company"
    client.bridgeSessionToken="wb1_abcdefghijklmnopqrstuvwxyz0123456789ABCDE12"
    if err:=client.RevokeBridgeSession(context.Background());err==nil {
        t.Fatal("Rejected server revocation reported success")
    }
    // The UI must still call Logout even if server-side revoke fails.
    client.Logout()
    if client.bridgeSessionToken!=""||client.accessToken!=""{
        t.Fatal("Logout retained sensitive credentials")
    }
}
