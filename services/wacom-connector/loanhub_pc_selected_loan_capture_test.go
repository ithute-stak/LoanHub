package main

import (
    "net/http/httptest"
    "net/url"
    "strings"
    "testing"
)

func TestSelectedLoanRequiresDocumentConsentBeforeCapture(t *testing.T) {
    called:=false
    ui:=&pcUI{sdkCapture:func()(disposableWacomPreview,error){
        called=true
        return disposableWacomPreview{},nil
    }}
    session:=&pcUISession{
        client:&LoanHubPCClient{},
        selectedLoanID:"12345678-1234-4234-8234-123456789012",
    }
    form:=url.Values{
        "signer_kind":{"client"},
        "consent":{"yes"},
        "consent_reference":{"TEST-CONSENT"},
        "confirm_name":{"Test Borrower"},
    }
    req:=httptest.NewRequest("POST","http://127.0.0.1:8767/capture",strings.NewReader(form.Encode()))
    req.Header.Set("Content-Type","application/x-www-form-urlencoded")
    if err:=req.ParseForm();err!=nil {t.Fatal(err)}
    ui.captureRequest(req,session)
    if called || session.capture!=nil || !strings.Contains(session.feedback,"Review the selected loan PDF") {
        t.Fatalf("capture was not blocked before document consent: %q",session.feedback)
    }
}

func TestSelectedLoanRejectsMissingDocumentIntentIdentifier(t *testing.T) {
    called:=false
    ui:=&pcUI{sdkCapture:func()(disposableWacomPreview,error){
        called=true
        return disposableWacomPreview{},nil
    }}
    session:=&pcUISession{
        client:&LoanHubPCClient{},
        selectedLoanID:"12345678-1234-4234-8234-123456789012",
        documentIntent:&LoanHubDocumentIntent{IntentID:"   ",Status:"consented"},
    }
    form:=url.Values{
        "signer_kind":{"client"},"consent":{"yes"},
        "consent_reference":{"TEST-CONSENT"},"confirm_name":{"Test Borrower"},
    }
    req:=httptest.NewRequest("POST","http://127.0.0.1:8767/capture",strings.NewReader(form.Encode()))
    req.Header.Set("Content-Type","application/x-www-form-urlencoded")
    if err:=req.ParseForm();err!=nil {t.Fatal(err)}
    ui.captureRequest(req,session)
    if called || session.capture!=nil {
        t.Fatal("capture accepted a selected loan without exact document intent ID")
    }
}
