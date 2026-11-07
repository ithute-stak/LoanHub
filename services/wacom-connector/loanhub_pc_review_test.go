package main

// Synthetic contract tests for the complete local reviewer workflow.
// These are code-only checks; no PC tablet, customer, VPS or signing.
import (
    "context"
    "encoding/json"
    "io"
    "net/http"
    "net/http/httptest"
    "strings"
    "testing"
)

const reviewTestID = "8b94b0dd-912b-4f0c-bef0-2144e50863a1"
const reviewTestCompany = "cf990032-8aac-4e4d-98f8-ab32c8c3c290"

func reviewTestClient(t *testing.T, handler http.HandlerFunc) (*LoanHubPCClient,func()) {
    t.Helper()
    server:=httptest.NewTLSServer(handler)
    client,err:=NewLoanHubPCClient(server.URL,server.Client())
    if err!=nil {server.Close();t.Fatal(err)}
    client.accessToken="SYNTHETIC-TOKEN-ONLY"
    client.companyID=reviewTestCompany
    return client,server.Close
}

func TestIndependentReviewQueuePreviewAndDecision(t *testing.T){
    png:=[]byte{137,80,78,71,13,10,26,10,0,0,0,0}
    count:=0
    client,done:=reviewTestClient(t,func(w http.ResponseWriter,r *http.Request){
        if r.Header.Get("Authorization")!="Bearer SYNTHETIC-TOKEN-ONLY" ||
            r.Header.Get("X-Company-ID")!=reviewTestCompany {t.Error("missing verified tenant token")}
        count++
        switch {
        case r.Method=="GET" && r.URL.Path=="/api/v1/local-signatures/review":
            if r.URL.Query().Get("limit")!="20" {t.Error("invalid review page limit")}
            w.Header().Set("Content-Type","application/json")
            _=json.NewEncoder(w).Encode(map[string]any{"captures":[]map[string]any{{
                "capture_file_id":reviewTestID,"company_id":reviewTestCompany,
                "signer_kind":"operator","evidence_status":"pending_review",
                "scan_status":"clean","usable_for_signing":false,
                "automatic_reuse_allowed":false,
            }}})
        case r.Method=="GET" && r.URL.Path=="/api/v1/local-signatures/review/"+reviewTestID+"/preview":
            w.Header().Set("Content-Type","image/png")
            _,_=w.Write(png)
        case r.Method=="POST" && r.URL.Path=="/api/v1/local-signatures/review/"+reviewTestID+"/decision":
            var decision map[string]any
            if err:=json.NewDecoder(r.Body).Decode(&decision);err!=nil{t.Error(err)}
            if decision["decision"]!="verify" || decision["identity_checked"]!=true ||
                decision["consent_checked"]!=true {t.Error("consent and identity review missing")}
            w.Header().Set("Content-Type","application/json")
            _=json.NewEncoder(w).Encode(map[string]any{
                "capture_file_id":reviewTestID,"company_id":reviewTestCompany,
                "evidence_status":"verified","usable_for_signing":false,
                "automatic_reuse_allowed":false,
            })
        default:
            http.NotFound(w,r)
        }
    })
    defer done()
    queue,err:=client.ReviewQueue(context.Background())
    if err!=nil || len(queue)!=1 {t.Fatalf("queue unavailable: %v",err)}
    got,err:=client.ReviewPreview(context.Background(),reviewTestID)
    if err!=nil || string(got)!=string(png) {t.Fatalf("preview unavailable: %v",err)}
    decision,err:=client.ReviewDecision(context.Background(),reviewTestID,
        "verify","TEST-REVIEW-1234","Synthetic identity and consent checked",true,true)
    if err!=nil || decision.EvidenceStatus!="verified" || decision.UsableForSigning {
        t.Fatalf("unsafe review decision: %v",err)
    }
    if count!=3 {t.Fatalf("unexpected backend calls: %d",count)}
}

func TestIndependentReviewRejectsCrossTenantQueue(t *testing.T){
    client,done:=reviewTestClient(t,func(w http.ResponseWriter,r *http.Request){
        w.Header().Set("Content-Type","application/json")
        _,_=io.WriteString(w,`{"captures":[{"capture_file_id":"8b94b0dd-912b-4f0c-bef0-2144e50863a1","company_id":"WRONG-COMPANY","evidence_status":"pending_review","scan_status":"clean","usable_for_signing":false}]}`)
    })
    defer done()
    if _,err:=client.ReviewQueue(context.Background());err==nil {
        t.Fatal("cross-company review evidence must be denied")
    }
}

func TestIndependentReviewCannotSignOrSkipConsent(t *testing.T){
    calls:=0
    client,done:=reviewTestClient(t,func(w http.ResponseWriter,r *http.Request){
        calls++
        w.Header().Set("Content-Type","application/json")
        _,_=io.WriteString(w,`{"capture_file_id":"8b94b0dd-912b-4f0c-bef0-2144e50863a1","company_id":"cf990032-8aac-4e4d-98f8-ab32c8c3c290","evidence_status":"verified","usable_for_signing":true}`)
    })
    defer done()
    _,err:=client.ReviewDecision(context.Background(),reviewTestID,"verify",
        "TEST-REVIEW-1234","Enough reason to review",false,true)
    if err==nil || calls!=0 {t.Fatal("missing identity check must stop before HTTP")}
    _,err=client.ReviewDecision(context.Background(),reviewTestID,"verify",
        "TEST-REVIEW-1234","Enough reason to review",true,true)
    if err==nil || !strings.Contains(err.Error(),"unsafe") {t.Fatal("cannot accept a signing-enabled review receipt")}
    if calls!=1 {t.Fatal("unexpected review requests")}
}
