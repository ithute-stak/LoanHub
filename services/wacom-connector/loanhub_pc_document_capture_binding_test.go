package main

import (
    "context"
    "net/http/httptest"
    "net/url"
    "strings"
    "testing"
    "time"
)

func TestDocumentPreparationDiscardsPreviousInk(t *testing.T) {
    ui,err:=newPCUI("https://loanhub.example")
    if err!=nil {t.Fatal(err)}
    png:=[]byte{1,2,3}
    session:=&pcUISession{
        capture:&pcPendingCapture{preview:disposableWacomPreview{PNG:png}},
        documentIntent:&LoanHubDocumentIntent{IntentID:"old"},
        lastDocumentCaptureID:"old-upload",
    }
    request:=httptest.NewRequest("POST",pcUIOrigin+"/document-prepare",strings.NewReader(""))
    ui.documentPrepareRequest(context.Background(),request,session)
    if session.capture!=nil || session.documentIntent!=nil || session.lastDocumentCaptureID!="" {
        t.Fatal("new document preparation retained prior evidence")
    }
    for _,v:=range png {if v!=0 {t.Fatal("signature PNG was not wiped")}}
}

func TestUploadRejectsCaptureFromDifferentDocumentConsent(t *testing.T) {
    cases:=[]struct{name,kind,borrower,consent,status string}{
        {"wrong-reference","client","borrower-1","old-consent","consented"},
        {"wrong-borrower","client","borrower-2","new-consent","consented"},
        {"wrong-signer","operator","borrower-1","new-consent","consented"},
        {"not-consented","client","borrower-1","new-consent","prepared"},
    }
    for _,tc:=range cases {
        t.Run(tc.name,func(t *testing.T){
            png:=[]byte{1,2,3}
            session:=&pcUISession{
                client:&LoanHubPCClient{},
                capture:&pcPendingCapture{
                    preview:disposableWacomPreview{PNG:png},
                    signerKind:tc.kind,borrowerID:tc.borrower,
                    consentReference:tc.consent,expires:time.Now().Add(time.Minute),
                },
                documentIntent:&LoanHubDocumentIntent{
                    BorrowerID:"borrower-1",ConsentReference:"new-consent",Status:tc.status,
                },
                lastDocumentCaptureID:"stale-upload",
            }
            form:=url.Values{"approved":{"yes"}}
            request:=httptest.NewRequest("POST",pcUIOrigin+"/upload",strings.NewReader(form.Encode()))
            request.Header.Set("Content-Type","application/x-www-form-urlencoded")
            if err:=request.ParseForm();err!=nil {t.Fatal(err)}
            ui:=&pcUI{}
            ui.uploadRequest(context.Background(),request,session)
            if session.capture!=nil || session.lastDocumentCaptureID!="" ||
                !strings.Contains(session.feedback,"Document consent changed") {
                t.Fatal("changed document consent did not fail closed")
            }
            for _,v:=range png {if v!=0 {t.Fatal("rejected signature bytes not wiped")}}
        })
    }
}

func TestUploadRejectsDifferentIntentWithSameConsentReference(t *testing.T) {
    png:=[]byte{1,2,3}
    session:=&pcUISession{
        client:&LoanHubPCClient{},
        capture:&pcPendingCapture{
            preview:disposableWacomPreview{PNG:png},
            signerKind:"client",borrowerID:"borrower-1",
            documentIntentID:"intent-original",
            consentReference:"same-consent",expires:time.Now().Add(time.Minute),
        },
        documentIntent:&LoanHubDocumentIntent{
            IntentID:"intent-replaced",BorrowerID:"borrower-1",
            ConsentReference:"same-consent",Status:"consented",
        },
    }
    form:=url.Values{"approved":{"yes"}}
    request:=httptest.NewRequest("POST",pcUIOrigin+"/upload",strings.NewReader(form.Encode()))
    request.Header.Set("Content-Type","application/x-www-form-urlencoded")
    if err:=request.ParseForm();err!=nil {t.Fatal(err)}
    (&pcUI{}).uploadRequest(context.Background(),request,session)
    if session.capture!=nil || !strings.Contains(session.feedback,"Document consent changed") {
        t.Fatal("signature capture was reused for a different document intent")
    }
    for _,v:=range png {if v!=0 {t.Fatal("rejected ink was not wiped")}}
}

func TestUploadRejectsDocumentIntentRemovedAfterCapture(t *testing.T) {
    png:=[]byte{1,2,3}
    session:=&pcUISession{
        client:&LoanHubPCClient{},
        capture:&pcPendingCapture{
            preview:disposableWacomPreview{PNG:png},
            signerKind:"client",borrowerID:"borrower-1",
            documentIntentID:"intent-original",
            consentReference:"consent-001",expires:time.Now().Add(time.Minute),
        },
    }
    form:=url.Values{"approved":{"yes"}}
    request:=httptest.NewRequest("POST",pcUIOrigin+"/upload",strings.NewReader(form.Encode()))
    request.Header.Set("Content-Type","application/x-www-form-urlencoded")
    if err:=request.ParseForm();err!=nil {t.Fatal(err)}
    (&pcUI{}).uploadRequest(context.Background(),request,session)
    if session.capture!=nil || !strings.Contains(session.feedback,"Document consent changed") {
        t.Fatal("capture retained after document intent was removed")
    }
    for _,v:=range png {if v!=0 {t.Fatal("stale signature bytes were not wiped")}}
}
