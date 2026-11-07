package main

// End-to-end local PC form -> TLS LoanHub API protocol contract verification.
// No device, user credentials, production API, database, or real signatures.
import (
    "bytes"
    "crypto/sha256"
    "encoding/base64"
    "encoding/hex"
    "encoding/json"
    "net/http"
    "net/http/httptest"
    "net/url"
    "strings"
    "testing"
    "time"
)

func TestPCToLoanHubSyntheticCaptureUploadAndReviewReceipt(t *testing.T) {
    const companyID = "4236a21f-5164-48aa-90f3-a35eccd23ae2"
    const borrowerID = "b8a9099b-694b-441b-b4a0-2d8394b7e62d"
    const nationalID = "SYNTHETIC-ONLY-001"
    preview := testPCPreview(t)
    requests := []string{}
    uploads := 0

    backend := httptest.NewTLSServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
        requests = append(requests, r.URL.Path)
        w.Header().Set("Content-Type", "application/json")
        if r.URL.Path != "/api/v1/auth/login" {
            if r.Header.Get("Authorization") != "Bearer synthetic-test-token" ||
                r.Header.Get("X-Company-ID") != companyID {
                t.Error("protected LoanHub request lacks correct tenant/token")
                http.Error(w, "unauthorized", http.StatusUnauthorized)
                return
            }
        }
        switch r.URL.Path {
        case "/api/v1/auth/login":
            if r.Method != http.MethodPost {
                t.Error("wrong login HTTP method")
            }
            var request struct { Phone string `json:"phone"`; Password string `json:"password"` }
            if err := json.NewDecoder(r.Body).Decode(&request); err != nil {
                t.Error(err)
            }
            if request.Phone != "59000000" || request.Password != "synthetic-password" {
                t.Error("unexpected synthetic login")
            }
            _, _ = w.Write([]byte(`{"access_token":"synthetic-test-token","token_type":"bearer","user":{"is_active":true,"id":"00000000-0000-4000-8000-000000000001","memberships":[{"company_id":"`+companyID+`","is_active":true}]}}`))
        case "/api/v1/local-signatures/me/status":
            _, _ = w.Write([]byte(`{"operator_id":"00000000-0000-4000-8000-000000000001","company_id":"`+companyID+`","full_name":"Synthetic Operator","signature_status":"missing","requires_capture":true,"usable_for_signing":false}`))
        case "/api/v1/local-signatures/clients/lookup":
            var request struct { NationalID string `json:"national_id"` }
            if err := json.NewDecoder(r.Body).Decode(&request); err != nil { t.Error(err) }
            if request.NationalID != nationalID { t.Errorf("unexpected client lookup: %q", request.NationalID) }
            _, _ = w.Write([]byte(`{"status":"matched","client":{"borrower_id":"`+borrowerID+`","full_name":"Synthetic Client","signature_status":"missing","requires_capture":true},"may_reuse":false,"may_sign_contract":false}`))
        case "/api/v1/local-signatures/captures":
            uploads++
            if r.Method != http.MethodPost { t.Error("wrong upload HTTP method") }
            var request struct {
                SignerKind string `json:"signer_kind"`
                BorrowerID string `json:"borrower_id"`
                ConsentReference string `json:"consent_reference"`
                CapturePNGBase64 string `json:"capture_png_base64"`
                CaptureSHA256 string `json:"capture_sha256"`
            }
            if err := json.NewDecoder(r.Body).Decode(&request); err != nil { t.Error(err) }
            raw, err := base64.StdEncoding.DecodeString(request.CapturePNGBase64)
            if err != nil { t.Error(err) }
            digest := sha256.Sum256(raw)
            if request.SignerKind != "client" || request.BorrowerID != borrowerID ||
                request.ConsentReference != "SYNTHETIC-CONSENT-001" ||
                !bytes.Equal(raw, preview.PNG) || request.CaptureSHA256 != hex.EncodeToString(digest[:]) {
                t.Error("uploaded signature not tied to verified borrower, digest and consent")
            }
            w.WriteHeader(http.StatusAccepted)
            _, _ = w.Write([]byte(`{"status":"pending_review","file_id":"55555555-5555-4555-8555-555555555555","duplicate":false,"usable_for_signing":false}`))
        default:
            t.Errorf("unexpected backend call %q",r.URL.Path)
            http.NotFound(w,r)
        }
    }))
    defer backend.Close()
    ui, err := newPCUI(backend.URL)
    if err != nil { t.Fatal(err) }
    ui.transport = backend.Client()
    captures := 0
    ui.sdkCapture = func() (disposableWacomPreview,error) {
        captures++
        return preview,nil
    }
    cookie, csrf, _ := localUIGet(t,ui)
    submit := func(path string, values url.Values) string {
        t.Helper()
        values.Set("csrf",csrf)
        response := localUIPost(ui,cookie,path,values,pcUIOrigin)
        if response.Code != 200 {
            t.Fatalf("%s: local HTTP %d: %s",path,response.Code,response.Body.String())
        }
        return response.Body.String()
    }

    loginPage := submit("/login",url.Values{
        "phone":{"59000000"},"password":{"synthetic-password"},"company":{companyID},
    })
    if !strings.Contains(loginPage,"Synthetic Operator") { t.Fatal("operator login/status not displayed") }
    submit("/lookup",url.Values{"national_id":{nationalID}})
    if uploads!=0 { t.Fatal("lookup unexpectedly uploaded a signature") }

    submit("/capture",url.Values{
        "signer_kind":{"client"},"confirm_name":{"Wrong name"},
        "consent_reference":{"SYNTHETIC-CONSENT-001"},"consent":{"yes"},
    })
    if captures!=0 || uploads!=0 { t.Fatal("wrong signer name started hardware or uploaded") }

    submit("/capture",url.Values{
        "signer_kind":{"client"},"confirm_name":{"Synthetic Client"},
        "consent_reference":{"SYNTHETIC-CONSENT-001"},
    })
    if captures!=0 || uploads!=0 { t.Fatal("missing consent started capture") }

    ready := submit("/capture",url.Values{
        "signer_kind":{"client"},"confirm_name":{"Synthetic Client"},
        "consent_reference":{"SYNTHETIC-CONSENT-001"},"consent":{"yes"},
    })
    if captures!=1 || uploads!=0 || !strings.Contains(ready,"/preview") {
        t.Fatal("local capture did not require a second explicit upload confirmation")
    }
    req:=httptest.NewRequest(http.MethodGet,pcUIOrigin+"/preview",nil)
    req.AddCookie(cookie)
    rec:=httptest.NewRecorder()
    ui.ServeHTTP(rec,req)
    if rec.Code!=http.StatusOK || !bytes.Equal(rec.Body.Bytes(),preview.PNG) {
        t.Fatal("handwriting review did not return exact captured PNG")
    }
    submit("/upload",url.Values{})
    if uploads!=0 { t.Fatal("upload without explicit review approval") }
    result:=submit("/upload",url.Values{"approved":{"yes"}})
    if uploads!=1 || !strings.Contains(result,"LoanHub received the capture") ||
        strings.Contains(result,"/preview") || strings.Contains(result,"Synthetic Client") {
        t.Fatal("upload not acknowledged or pending image/client data retained")
    }
    session := testPCSession(ui,cookie)
    if session.capture!=nil || session.lastClient!=nil || session.status!=nil {
        t.Fatal("sensitive capture and search state not cleared after upload")
    }
    req=httptest.NewRequest(http.MethodGet,pcUIOrigin+"/preview",nil)
    req.AddCookie(cookie)
    rec=httptest.NewRecorder()
    ui.ServeHTTP(rec,req)
    if rec.Code!=http.StatusNotFound { t.Fatal("submitted image still available via preview") }
    if len(requests)!=4 {
        t.Fatalf("expected login, status, lookup, upload only; got %v", requests)
    }
    submit("/logout",url.Values{})
    if session.client!=nil { t.Fatal("logout did not clear auth session") }
}

func TestPCExpiredCaptureNeverUploads(t *testing.T) {
    ui,cookie,csrf:=testPCUIWithCapture(t)
    session:=testPCSession(ui,cookie)
    session.client=&LoanHubPCClient{}
    session.status=&LoanHubOperatorStatus{RequiresCapture:true}
    session.capture=&pcPendingCapture{
        signerKind:"operator",consentReference:"TEST-001",Label:"Synthetic Operator",
        preview:testPCPreview(t),expires:time.Now().Add(-time.Second),
    }
    res:=localUIPost(ui,cookie,"/upload",url.Values{
        "csrf":{csrf},"approved":{"yes"},
    },pcUIOrigin)
    if res.Code!=200 || session.capture!=nil ||
        !strings.Contains(res.Body.String(),"Capture expired") {
        t.Fatal("expired capture was not discarded before network upload")
    }
}
