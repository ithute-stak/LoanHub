package main

import (
    "context"
    "encoding/json"
    "net/http"
    "testing"
)

func TestFindClientByBorrowerIDUsesTenantScopedEndpoint(t *testing.T) {
    const borrower = "b8a9099b-694b-441b-b4a0-2d8394b7e62d"
    calls := 0
    client, server := newTestLoanHubPC(t, func(w http.ResponseWriter, r *http.Request) {
        calls++
        if r.Method != http.MethodGet ||
            r.URL.Path != "/api/v1/local-signatures/clients/by-borrower/"+borrower ||
            r.Header.Get("Authorization") != "Bearer synthetic-token" ||
            r.Header.Get("X-Company-ID") != "synthetic-company" {
            t.Fatal("borrower lookup did not preserve authenticated company scope")
        }
        w.Header().Set("Content-Type", "application/json")
        _ = json.NewEncoder(w).Encode(map[string]any{
            "status": "matched",
            "client": map[string]any{"borrower_id": borrower, "full_name": "Synthetic Borrower",
                "signature_status": "missing", "requires_capture": true},
            "may_reuse": false, "may_sign_contract": false,
        })
    })
    defer server.Close()
    client.accessToken = "synthetic-token"
    client.companyID = "synthetic-company"
    result, err := client.FindClientByBorrowerID(context.Background(), borrower)
    if err != nil || result.Client == nil || result.Client.BorrowerID != borrower || calls != 1 {
        t.Fatalf("borrower lookup failed: %v", err)
    }
}

func TestFindClientByBorrowerIDRejectsMismatchedIdentity(t *testing.T) {
    const borrower = "b8a9099b-694b-441b-b4a0-2d8394b7e62d"
    client, server := newTestLoanHubPC(t, func(w http.ResponseWriter, r *http.Request) {
        w.Header().Set("Content-Type", "application/json")
        _, _ = w.Write([]byte(`{"status":"matched","client":{"borrower_id":"11111111-1111-4111-8111-111111111111","full_name":"Other","signature_status":"missing","requires_capture":true},"may_reuse":false,"may_sign_contract":false}`))
    })
    defer server.Close()
    client.accessToken = "synthetic-token"
    client.companyID = "synthetic-company"
    if _, err := client.FindClientByBorrowerID(context.Background(), borrower); err == nil {
        t.Fatal("accepted another borrower's identity")
    }
}

func TestFindClientByBorrowerIDRejectsMalformedIDBeforeNetwork(t *testing.T) {
    client, server := newTestLoanHubPC(t, func(w http.ResponseWriter, r *http.Request) {
        t.Fatal("invalid borrower ID reached network")
    })
    defer server.Close()
    client.accessToken = "synthetic-token"
    client.companyID = "synthetic-company"
    for _, bad := range []string{"", "../bad", "11111111-1111-1111-1111-11111111111z"} {
        if _, err := client.FindClientByBorrowerID(context.Background(), bad); err == nil {
            t.Fatalf("accepted malformed borrower ID %q", bad)
        }
    }
}
