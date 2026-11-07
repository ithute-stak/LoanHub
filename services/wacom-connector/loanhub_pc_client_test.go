package main

import (
    "context"
    "encoding/json"
    "net/http"
    "net/http/httptest"
    "strings"
    "testing"
)

func newTestLoanHubPC(t *testing.T, h http.HandlerFunc) (*LoanHubPCClient, *httptest.Server) {
    t.Helper()
    server := httptest.NewTLSServer(h)
    client, err := NewLoanHubPCClient(server.URL, server.Client())
    if err != nil { server.Close(); t.Fatal(err) }
    return client, server
}

func TestLoanHubPCRejectsUnsafeOrigins(t *testing.T) {
    for _, origin := range []string{
        "http://loanhub.co.ls", "https://user:password@loanhub.co.ls",
        "https://loanhub.co.ls/other", "https://loanhub.co.ls?token=secret",
    } {
        if _, err := NewLoanHubPCClient(origin, nil); err == nil {
            t.Fatalf("accepted unsafe origin %q", origin)
        }
    }
}

func TestLoanHubPCLoginAndFindClient(t *testing.T) {
    company := "f8dc1d23-17c7-40fe-8094-f7e8e89a355c"
    requestCount := 0
    client, server := newTestLoanHubPC(t, func(w http.ResponseWriter, r *http.Request) {
        requestCount++
        w.Header().Set("Content-Type", "application/json")
        switch r.URL.Path {
        case "/api/v1/auth/login":
            if r.Header.Get("Authorization") != "" { t.Fatal("login must not include access token") }
            var login map[string]any
            if err := json.NewDecoder(r.Body).Decode(&login); err != nil { t.Fatal(err) }
            if login["phone"] != "59000000" || login["password"] != "synthetic-secret" ||
               login["otp"] != "123456" { t.Fatal("incorrect login fields") }
            _ = json.NewEncoder(w).Encode(map[string]any{
                "access_token": "synthetic-access", "token_type": "bearer",
                "user": map[string]any{"id": "operator", "is_active": true, "memberships": []any{
                    map[string]any{"company_id": company, "is_active": true},
                }},
            })
        case "/api/v1/local-signatures/clients/lookup":
            if r.Header.Get("Authorization") != "Bearer synthetic-access" ||
               r.Header.Get("X-Company-ID") != company { t.Fatal("tenant auth headers missing") }
            var lookup map[string]string
            if err := json.NewDecoder(r.Body).Decode(&lookup); err != nil { t.Fatal(err) }
            if lookup["national_id"] != "TEST-123" { t.Fatal("unexpected lookup query") }
            _ = json.NewEncoder(w).Encode(map[string]any{
                "status": "matched",
                "client": map[string]any{"borrower_id": "b8a9099b-694b-441b-b4a0-2d8394b7e62d",
                    "full_name": "Synthetic Client", "signature_status": "missing", "requires_capture": true},
                "may_reuse": false, "may_sign_contract": false,
            })
        default:
            t.Fatalf("unexpected path %s", r.URL.Path)
        }
    })
    defer server.Close()
    if err := client.Login(context.Background(), "59000000", "synthetic-secret", "123456", company); err != nil { t.Fatal(err) }
    result, err := client.FindClient(context.Background(), "TEST-123")
    if err != nil { t.Fatal(err) }
    if result.Client == nil || result.Client.FullName != "Synthetic Client" ||
       !result.Client.RequiresCapture || result.MaySignContract { t.Fatal("unexpected client result") }
    client.Logout()
    if _, err := client.FindClient(context.Background(), "TEST-123"); err == nil {
        t.Fatal("lookup allowed after logout")
    }
    if requestCount != 2 { t.Fatal("logout should not issue extra request") }
}

func TestLoanHubPCRejectsForeignMembership(t *testing.T) {
    client, server := newTestLoanHubPC(t, func(w http.ResponseWriter, r *http.Request) {
        w.Header().Set("Content-Type", "application/json")
        _, _ = w.Write([]byte(`{"access_token":"secret","token_type":"bearer","user":{"id":"one","memberships":[{"company_id":"other","is_active":true}]}}`))
    })
    defer server.Close()
    if err := client.Login(context.Background(), "59000000", "synthetic-password", "", "company-1"); err == nil {
        t.Fatal("cross-company login accepted")
    }
    if client.accessToken != "" { t.Fatal("token retained after rejected login") }
}

func TestLoanHubPCNeverFollowsRedirect(t *testing.T) {
    requests := 0
    client, server := newTestLoanHubPC(t, func(w http.ResponseWriter, r *http.Request) {
        requests++
        http.Redirect(w, r, "https://evil.example/", http.StatusFound)
    })
    defer server.Close()
    if err := client.Login(context.Background(), "59000000", "synthetic-password", "", "company-1"); err == nil ||
        !strings.Contains(err.Error(), "302") { t.Fatal("redirect must fail closed") }
    if requests != 1 { t.Fatalf("redirect followed %d", requests) }
}

func TestLoanHubPCUploadRejectsBadPNG(t *testing.T) {
    client, server := newTestLoanHubPC(t, func(w http.ResponseWriter, r *http.Request) {
        t.Fatal("invalid PNG must not reach backend")
    })
    defer server.Close()
    client.accessToken = "synthetic"
    client.companyID = "synthetic-company"
    _, err := client.UploadPNG(context.Background(), "operator", "", "consent-test", []byte("not png"))
    if err == nil { t.Fatal("bad PNG accepted") }
}

func TestLoanHubPCOperatorStatus(t *testing.T) {
    client, server := newTestLoanHubPC(t, func(w http.ResponseWriter, r *http.Request) {
        if r.Method != "GET" || r.URL.Path != "/api/v1/local-signatures/me/status" {
            t.Fatal("wrong request")
        }
        w.Header().Set("Content-Type", "application/json")
        _, _ = w.Write([]byte(`{"operator_id":"synthetic","company_id":"tenant","signature_status":"missing","requires_capture":true,"usable_for_signing":false}`))
    })
    defer server.Close()
    client.accessToken = "synthetic"
    client.companyID = "tenant"
    status, err := client.OperatorSignatureStatus(context.Background())
    if err != nil || !status.RequiresCapture || status.UsableForSigning { t.Fatal("invalid operator status", err) }
}
