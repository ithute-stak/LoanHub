package main

// Negative-path conformance tests for the real LoanHub capture API responses.
// Tests use an in-process HTTPS test server, never production infrastructure.
import (
    "context"
    "fmt"
    "net/http"
    "strings"
    "testing"
)

func TestLoanHubOperatorStatusFailsClosed(t *testing.T) {
    cases := []struct{ name, body string }{
        {"company mismatch", `{"operator_id":"test-operator","company_id":"another-company","signature_status":"missing","requires_capture":true,"usable_for_signing":false}`},
        {"signing unexpectedly enabled", `{"operator_id":"test-operator","company_id":"TEST-COMPANY","signature_status":"missing","requires_capture":true,"usable_for_signing":true}`},
        {"capture eligibility mismatch", `{"operator_id":"test-operator","company_id":"TEST-COMPANY","signature_status":"missing","requires_capture":false,"usable_for_signing":false}`},
        {"unrecognized signature status", `{"operator_id":"test-operator","company_id":"TEST-COMPANY","signature_status":"active","requires_capture":false,"usable_for_signing":false}`},
        {"missing identity", `{"company_id":"TEST-COMPANY","signature_status":"missing","requires_capture":true,"usable_for_signing":false}`},
    }
    for _, tc := range cases {
        t.Run(tc.name, func(t *testing.T) {
            client, server := newTestLoanHubPC(t, func(w http.ResponseWriter, r *http.Request) {
                if r.URL.Path != "/api/v1/local-signatures/me/status" {t.Error("wrong operator route")}
                if r.Header.Get("X-Company-ID") != "TEST-COMPANY" {t.Error("wrong tenant")}
                w.Header().Set("Content-Type", "application/json")
                _, _ = fmt.Fprint(w, tc.body)
            })
            defer server.Close()
            client.accessToken = "synthetic-only"
            client.companyID = "TEST-COMPANY"
            _, err := client.OperatorSignatureStatus(context.Background())
            if err == nil {t.Fatal("must refuse malformed, foreign or signing-enabled operator status")}
        })
    }
}

func TestLoanHubLookupFailsClosed(t *testing.T) {
    cases := []struct{name, body string}{
        {"automatic reuse", `{"status":"not_found","client":null,"may_reuse":true,"may_sign_contract":false}`},
        {"contract signing", `{"status":"matched","client":{"borrower_id":"test-id","full_name":"Synthetic Client","signature_status":"missing","requires_capture":true},"may_reuse":false,"may_sign_contract":true}`},
        {"unexpected unmatched identity", `{"status":"not_found","client":{"full_name":"Sensitive Name"},"may_reuse":false,"may_sign_contract":false}`},
        {"malformed status", `{"status":"enabled","client":null,"may_reuse":false,"may_sign_contract":false}`},
        {"inconsistent eligibility", `{"status":"matched","client":{"borrower_id":"test-id","full_name":"Synthetic Client","signature_status":"active","requires_capture":true},"may_reuse":false,"may_sign_contract":false}`},
        {"missing matched identity", `{"status":"matched","client":null,"may_reuse":false,"may_sign_contract":false}`},
    }
    for _,tc := range cases {
        t.Run(tc.name,func(t *testing.T){
            client,server:=newTestLoanHubPC(t,func(w http.ResponseWriter,r *http.Request){
                if r.URL.Path!="/api/v1/local-signatures/clients/lookup" {t.Error("wrong lookup path")}
                w.Header().Set("Content-Type","application/json")
                _,_=fmt.Fprint(w,tc.body)
            })
            defer server.Close()
            client.accessToken="synthetic-only"
            client.companyID="TEST-COMPANY"
            _,err:=client.FindClient(context.Background(),"TEST-ONLY-IDENTITY")
            if err==nil {t.Fatal("unsafe borrower lookup accepted")}
        })
    }
}

func TestLoanHubLookupRejectsInvalidNationalIDBeforeRequest(t *testing.T){
    calls:=0
    client,server:=newTestLoanHubPC(t,func(w http.ResponseWriter,r *http.Request){calls++})
    defer server.Close()
    client.accessToken="synthetic-only"
    client.companyID="TEST-COMPANY"
    for _,id:=range []string{"", "bad",strings.Repeat("T",51)} {
        if _,err:=client.FindClient(context.Background(),id);err==nil {
            t.Fatalf("invalid identifier length accepted: %d",len(id))
        }
    }
    if calls!=0 {t.Fatal("invalid identifier must not send personal data")}
}
