package main

import (
    "bytes"
    "context"
    "image"
    "image/color"
    "image/png"
    "net/http"
    "net/http/httptest"
    "net/url"
    "strings"
    "testing"
    "time"
)

func testPCPreview(t *testing.T) disposableWacomPreview {
    t.Helper()
    img:=image.NewRGBA(image.Rect(0,0,3,3))
    img.Set(0,0,color.Black)
    var buf bytes.Buffer
    if err:=png.Encode(&buf,img);err!=nil {t.Fatal(err)}
    return disposableWacomPreview{PNG:buf.Bytes(),ContactPoints:4,StrokeCount:1}
}

func testPCUIWithCapture(t *testing.T)(*pcUI,*http.Cookie,string) {
    t.Helper()
    ui,err:=newPCUI("https://loanhub.example")
    if err!=nil {t.Fatal(err)}
    ui.sdkCapture=func()(disposableWacomPreview,error){return testPCPreview(t),nil}
    cookie,csrf,_:=localUIGet(t,ui)
    return ui,cookie,csrf
}

func testPCSession(ui *pcUI,cookie *http.Cookie)*pcUISession {
    return ui.sessions[cookie.Value]
}

func TestPCCaptureRequiresAuthenticatedOperator(t *testing.T) {
    ui,cookie,csrf:=testPCUIWithCapture(t)
    payload:=url.Values{
        "csrf":{csrf},"signer_kind":{"operator"},
        "confirm_name":{"Synthetic Operator"},"consent_reference":{"consent-001"},"consent":{"yes"},
    }
    response:=localUIPost(ui,cookie,"/capture",payload,pcUIOrigin)
    if response.Code!=200 || testPCSession(ui,cookie).capture!=nil {
        t.Fatal("unauthenticated browser started capture")
    }
}

func TestPCCaptureRequiresIdentityAndConsent(t *testing.T) {
    ui,cookie,csrf:=testPCUIWithCapture(t)
    session:=testPCSession(ui,cookie)
    session.client=&LoanHubPCClient{}
    name:="Synthetic Operator"
    session.status=&LoanHubOperatorStatus{FullName:&name,RequiresCapture:true}
    called:=0
    ui.sdkCapture=func()(disposableWacomPreview,error){
        called++
        return testPCPreview(t),nil
    }
    body:=url.Values{
        "csrf":{csrf},"signer_kind":{"operator"},
        "confirm_name":{"Incorrect Name"},"consent_reference":{"consent-001"},"consent":{"yes"},
    }
    localUIPost(ui,cookie,"/capture",body,pcUIOrigin)
    if called!=0 || session.capture!=nil {t.Fatal("wrong identity started pad")}
    body.Set("confirm_name",name)
    body.Del("consent")
    localUIPost(ui,cookie,"/capture",body,pcUIOrigin)
    if called!=0 || session.capture!=nil {t.Fatal("missing consent started pad")}
    body.Set("consent","yes")
    response:=localUIPost(ui,cookie,"/capture",body,"https://evil.example")
    if response.Code!=403 || called!=0 {t.Fatal("foreign-origin capture allowed")}
    response=localUIPost(ui,cookie,"/capture",body,pcUIOrigin)
    if response.Code!=200 || called!=1 || session.capture==nil {
        t.Fatal("valid, consented operator capture was not prepared")
    }
    if !strings.Contains(response.Body.String(),"/preview") {
        t.Fatal("preview confirmation missing")
    }
}

func TestPCUploadRequiresSecondApprovalAndExpires(t *testing.T) {
    ui,cookie,csrf:=testPCUIWithCapture(t)
    session:=testPCSession(ui,cookie)
    session.client=&LoanHubPCClient{}
    session.status=&LoanHubOperatorStatus{RequiresCapture:true}
    session.capture=&pcPendingCapture{
        preview:testPCPreview(t),signerKind:"operator",
        consentReference:"consent-001",expires:time.Now().Add(time.Minute),
    }
    ui.uploadRequest(context.Background(),httptest.NewRequest(http.MethodPost,
        pcUIOrigin+"/upload",nil),session)
    if session.capture==nil {t.Fatal("unapproved capture consumed")}
    req:=httptest.NewRequest(http.MethodPost,pcUIOrigin+"/upload",nil)
    req.PostForm=url.Values{"approved":{"yes"}}
    session.capture.expires=time.Now().Add(-time.Second)
    ui.uploadRequest(context.Background(),req,session)
    if session.capture!=nil {t.Fatal("expired capture was not removed")}
    if session.feedback!="Capture expired; please capture again" {t.Fatal("expiry not reported")}
    // Ensure rejected submission from a foreign browser never reaches upload.
    response:=localUIPost(ui,cookie,"/upload",
        url.Values{"csrf":{csrf},"approved":{"yes"}},"https://evil.example")
    if response.Code!=403 {t.Fatal("foreign browser could submit upload")}
}

func TestPCPreviewRequiresSignedInOwner(t *testing.T) {
    ui,cookie,_:=testPCUIWithCapture(t)
    session:=testPCSession(ui,cookie)
    session.capture=&pcPendingCapture{
        preview:testPCPreview(t),expires:time.Now().Add(time.Minute),
    }
    req:=httptest.NewRequest(http.MethodGet,pcUIOrigin+"/preview",nil)
    req.AddCookie(cookie)
    recorder:=httptest.NewRecorder()
    ui.ServeHTTP(recorder,req)
    if recorder.Code!=404 {t.Fatal("preview served without authentication")}
    session.client=&LoanHubPCClient{}
    recorder=httptest.NewRecorder()
    ui.ServeHTTP(recorder,req)
    if recorder.Code!=200 || recorder.Header().Get("Content-Type")!="image/png" {
        t.Fatal("authenticated pending preview unavailable")
    }
    session.capture.expires=time.Now().Add(-time.Second)
    recorder=httptest.NewRecorder()
    ui.ServeHTTP(recorder,req)
    if recorder.Code!=404 {t.Fatal("expired preview served")}
}
