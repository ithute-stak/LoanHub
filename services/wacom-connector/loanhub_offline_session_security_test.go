package main

import (
    "context"
    "encoding/json"
    "net/http"
    "testing"
    "time"
)

// These tests use the repository's existing TLS mock to avoid any live LoanHub
// requests, physical signature capture or production credentials.
func TestOfflineWacomRevocationNeverSendsCapabilityToForeignEndpoint(t *testing.T) {
    token := "wb1_abcdefghijklmnopqrstuvwxyz0123456789ABCDE12"
    calls := 0
    client,server := newTestLoanHubPC(t,func(w http.ResponseWriter,r *http.Request) {
        calls++
        if r.URL.Path != "/api/v1/wacom-bridge/sessions/revoke" || r.Method != http.MethodPost {
            t.Fatal("Capability transmitted to unexpected route")
        }
        if r.Header.Get("Authorization") != "Bearer synthetic" ||
            r.Header.Get("X-Company-ID") != "synthetic-company" ||
            r.Header.Get("X-Wacom-Bridge-Session") != token {
            t.Fatal("Revocation lacked both credentials")
        }
        w.Header().Set("Content-Type","application/json")
        _ = json.NewEncoder(w).Encode(map[string]any{"revoked":true,"signing_authorized":false})
    })
    defer server.Close()
    client.accessToken="synthetic"
    client.companyID="synthetic-company"
    client.bridgeSessionToken=token
    client.bridgeSessionExpires=time.Now().Add(3*time.Minute)
    if err:=client.RevokeBridgeSession(context.Background());err!=nil { t.Fatal(err) }
    if client.bridgeSessionToken!=""||!client.bridgeSessionExpires.IsZero() {t.Fatal("Revocation retained session")}
    client.Logout()
    if client.accessToken!=""||client.operatorID!=""||client.bridgeSessionToken!="" {
        t.Fatal("Logout retained sensitive operator state")
    }
    if calls!=1 {t.Fatalf("Expected one signed-out session revocation, got %d",calls)}
}

func TestOfflineWacomUnauthorizedSessionCannotReportSigningPermission(t *testing.T) {
    client,server:=newTestLoanHubPC(t,func(w http.ResponseWriter,r *http.Request){
        w.Header().Set("Content-Type","application/json")
        _=json.NewEncoder(w).Encode(map[string]any{"revoked":true,"signing_authorized":true})
    })
    defer server.Close()
    client.accessToken="synthetic"
    client.companyID="synthetic-company"
    client.bridgeSessionToken="wb1_abcdefghijklmnopqrstuvwxyz0123456789ABCDE12"
    if err:=client.RevokeBridgeSession(context.Background());err==nil {
        t.Fatal("Unexpected signing-authorized revocation receipt accepted")
    }
    // Never block local credential destruction on a failed server call.
    client.Logout()
    if client.bridgeSessionToken!="" {t.Fatal("Client still holds unsafe token")}
}
