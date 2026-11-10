package main

import (
    "context"
    "crypto/sha256"
    "encoding/hex"
    "net/http"
    "net/http/httptest"
    "testing"
    "strings"
    "time"
)

func TestOriginalPDFRetrievalVerifiesExactBytesAndWorkstation(t *testing.T) {
    original:=[]byte("%PDF-1.4\nsynthetic document\n%%EOF")
    sum:=sha256.Sum256(original)
    digest:=hex.EncodeToString(sum[:])
    intentID:="12345678-1234-4234-8234-123456789012"
    companyID:="22345678-1234-4234-8234-123456789012"
    calls:=0
    api:=httptest.NewTLSServer(http.HandlerFunc(func(w http.ResponseWriter,r *http.Request){
        calls++
        if r.URL.Path!="/api/v1/wacom-document-intents/"+intentID+"/source-pdf" ||
            r.Header.Get("Authorization")!="Bearer synthetic" ||
            r.Header.Get("X-Company-ID")!=companyID ||
            r.Header.Get("X-Wacom-Bridge-Session")!="wb1_synthetic" {
            t.Error("missing workstation or account authorization")
            http.Error(w,"forbidden",http.StatusForbidden)
            return
        }
        w.Header().Set("Content-Type","application/pdf")
        w.Header().Set("X-Wacom-Original-SHA256",digest)
        w.Header().Set("X-Wacom-Signing-Authorized","false")
        _,_=w.Write(original)
    }))
    defer api.Close()
    client,err:=NewLoanHubPCClient(api.URL,api.Client())
    if err!=nil {t.Fatal(err)}
    client.accessToken="synthetic"
    client.operatorID="employee"
    client.companyID=companyID
    client.workstationKeyDir="/synthetic/private"
    client.bridgeSessionToken="wb1_synthetic"
    client.bridgeSessionExpires=time.Now().Add(time.Minute)
    intent:=LoanHubDocumentIntent{
        IntentID:intentID,CompanyID:companyID,DocumentSHA256:digest,Status:"prepared",
    }
    pdf,err:=client.FetchOriginalContractPDF(context.Background(),intent)
    if err!=nil || string(pdf)!=string(original) || calls!=1 {
        t.Fatalf("verified original preview failed: %v, calls=%d",err,calls)
    }
    intent.DocumentSHA256=hex.EncodeToString(make([]byte,32))
    if _,err:=client.FetchOriginalContractPDF(context.Background(),intent);err==nil {
        t.Fatal("tampered expected hash was accepted")
    }
    intent.CompanyID="32345678-1234-4234-8234-123456789012"
    if _,err:=client.FetchOriginalContractPDF(context.Background(),intent);err==nil {
        t.Fatal("cross-company original preview was accepted")
    }
}

func TestLocalPreviewDeniesUnboundOrUnavailableSession(t *testing.T) {
    ui,err:=newPCUI("https://loanhub.example")
    if err!=nil {t.Fatal(err)}
    cookie,_,_:=localUIGet(t,ui)
    req:=httptest.NewRequest(http.MethodGet,pcUIOrigin+"/document-preview",nil)
    req.AddCookie(cookie)
    recorder:=httptest.NewRecorder()
    ui.ServeHTTP(recorder,req)
    if recorder.Code!=http.StatusForbidden {
        t.Fatalf("unauthenticated original preview returned %d",recorder.Code)
    }
    if recorder.Header().Get("Cache-Control")!="no-store" {
        t.Fatal("local preview was cacheable")
    }
}

func TestLocalPDFPreviewAllowsOnlySameOriginFraming(t *testing.T) {
    ui,err:=newPCUI("https://loanhub.example")
    if err!=nil {t.Fatal(err)}
    cookie,_,_:=localUIGet(t,ui)
    request:=httptest.NewRequest(http.MethodGet,pcUIOrigin+"/document-preview",nil)
    request.AddCookie(cookie)
    result:=httptest.NewRecorder()
    ui.ServeHTTP(result,request)
    // The missing authenticated document must still be rejected.
    if result.Code!=http.StatusForbidden {t.Fatalf("unauthorized preview: %d",result.Code)}
    if result.Header().Get("X-Frame-Options")!="SAMEORIGIN" ||
        !strings.Contains(result.Header().Get("Content-Security-Policy"),"frame-ancestors 'self'") {
        t.Fatal("same-origin PDF frame remains blocked")
    }
    pageRequest:=httptest.NewRequest(http.MethodGet,pcUIOrigin+"/",nil)
    pageResult:=httptest.NewRecorder()
    ui.ServeHTTP(pageResult,pageRequest)
    if !strings.Contains(pageResult.Header().Get("Content-Security-Policy"),"frame-ancestors 'none'") {
        t.Fatal("ordinary UI lost clickjacking protection")
    }
}
