package main

// Browser form integration: LoanHub management review is separated from the
// capture session, requires CSRF, and never authorizes document signing.
import (
    "encoding/json"
    "net/http"
    "net/http/httptest"
    "net/url"
    "strings"
    "testing"
)

func TestLocalPCIndependentReviewerBrowserFlow(t *testing.T) {
    company:=reviewTestCompany
    decisions:=0
    backend:=httptest.NewTLSServer(http.HandlerFunc(func(w http.ResponseWriter,r *http.Request){
        w.Header().Set("Content-Type","application/json")
        switch {
        case r.URL.Path=="/api/v1/auth/login" && r.Method==http.MethodPost:
            _=json.NewEncoder(w).Encode(map[string]any{
                "access_token":"synthetic-review-token", "token_type":"bearer",
                "user":map[string]any{"id":"synthetic-manager","is_active":true,
                    "memberships":[]any{map[string]any{"company_id":company,"is_active":true}}},
            })
        case r.URL.Path=="/api/v1/local-signatures/me/status":
            if r.Header.Get("Authorization")!="Bearer synthetic-review-token" {t.Error("missing bearer token")}
            _=json.NewEncoder(w).Encode(map[string]any{
                "operator_id":"synthetic-manager","company_id":company,
                "signature_status":"missing","requires_capture":true,"usable_for_signing":false,
                "full_name":"Synthetic Reviewer",
            })
        case r.URL.Path=="/api/v1/local-signatures/review" && r.Method==http.MethodGet:
            if r.Header.Get("X-Company-ID")!=company {t.Error("review accessed wrong tenant")}
            _=json.NewEncoder(w).Encode(map[string]any{
                "captures":[]any{map[string]any{
                    "capture_file_id":reviewTestID,"company_id":company,
                    "signer_kind":"client","signer_id":"synthetic-borrower",
                    "evidence_status":"pending_review","scan_status":"clean",
                    "usable_for_signing":false,"automatic_reuse_allowed":false,
                }},
            })
        case r.URL.Path=="/api/v1/local-signatures/review/"+reviewTestID+"/decision":
            decisions++
            var form map[string]any
            if err:=json.NewDecoder(r.Body).Decode(&form);err!=nil{t.Error(err)}
            if form["decision"]!="reject" || form["identity_checked"]!=false ||
                form["consent_checked"]!=false {t.Error("unexpected review decision")}
            _=json.NewEncoder(w).Encode(map[string]any{
                "capture_file_id":reviewTestID,"company_id":company,
                "evidence_status":"rejected","usable_for_signing":false,
                "automatic_reuse_allowed":false,
            })
        default:
            http.NotFound(w,r)
        }
    }))
    defer backend.Close()
    ui,err:=newPCUI(backend.URL)
    if err!=nil{t.Fatal(err)}
    ui.transport=backend.Client()
    cookie,csrf,_:=localUIGet(t,ui)
    submit:=func(path string,params url.Values)string{
        t.Helper()
        params.Set("csrf",csrf)
        response:=localUIPost(ui,cookie,path,params,pcUIOrigin)
        if response.Code!=http.StatusOK {t.Fatalf("%s failed: %d",path,response.Code)}
        return response.Body.String()
    }
    submit("/login",url.Values{
        "phone":{"59000000"},"password":{"synthetic-only-password"},
        "company":{company},
    })
    page:=submit("/review-refresh",url.Values{})
    if !strings.Contains(page,reviewTestID) || !strings.Contains(page,"synthetic-borrower") {
        t.Fatal("pending review UI did not display scoped evidence")
    }

    // The server checks CSRF even when the browser shows a valid review item.
    rejected:=localUIPost(ui,cookie,"/review-decision",url.Values{
        "csrf":{"wrong"},"file_id":{reviewTestID},"decision":{"reject"},
        "evidence_reference":{"TEST-REVIEW-001"},
        "reason":{"Invalid synthetic test evidence"},
    },pcUIOrigin)
    if rejected.Code!=http.StatusForbidden || decisions!=0 {t.Fatal("review accepted invalid CSRF")}

    result:=submit("/review-decision",url.Values{
        "file_id":{reviewTestID},"decision":{"reject"},
        "evidence_reference":{"TEST-REVIEW-001"},
        "reason":{"Invalid synthetic test evidence"},
    })
    if decisions!=1 || !strings.Contains(result,"No document signing or reuse enabled") {
        t.Fatal("review decision absent or unsafe")
    }
    session:=testPCSession(ui,cookie)
    if len(session.reviewQueue)!=0 {t.Fatal("review queue must be invalidated after decision")}
    submit("/logout",url.Values{})
    if session.client!=nil {t.Fatal("reviewer logout failed to clear token")}
}
