package main

// Offline-only tests. Never access a real tablet or LoanHub network.
import (
    "bytes"
    "net/http/httptest"
    "net/url"
    "strings"
    "testing"
    "time"
)

func TestPCRejectedSDKPreviewIsZeroized(t *testing.T) {
    png := []byte{137,80,78,71,13,10,26,10,1,2,3,4,5}
    count := 0
    ui := &pcUI{sdkCapture:func()(disposableWacomPreview,error){
        count++
        return disposableWacomPreview{PNG:png,ContactPoints:0,StrokeCount:0},nil
    }}
    name := "Synthetic Operator"
    session := &pcUISession{
        client:&LoanHubPCClient{},
        status:&LoanHubOperatorStatus{FullName:&name,RequiresCapture:true},
    }
    request := httptest.NewRequest("POST","http://127.0.0.1:8767/capture",
        strings.NewReader(url.Values{
            "signer_kind":{"operator"},
            "consent_reference":{"SYNTHETIC-REFERENCE"},
            "confirm_name":{name},
            "consent":{"yes"},
        }.Encode()))
    request.Header.Set("Content-Type","application/x-www-form-urlencoded")
    if err:=request.ParseForm();err!=nil {t.Fatal(err)}
    ui.captureRequest(request,session)
    if count!=1 || session.capture!=nil {t.Fatal("invalid capture was accepted")}
    if !bytes.Equal(png,make([]byte,len(png))) {t.Fatal("rejected capture remains in RAM")}
}

func TestPCDiscardZeroizesExistingPNG(t *testing.T) {
    png:=[]byte{1,2,3,4,5,6}
    session:=&pcUISession{capture:&pcPendingCapture{
        preview:disposableWacomPreview{PNG:png},expires:time.Now().Add(time.Minute),
    }}
    session.discardCapture()
    if session.capture!=nil || !bytes.Equal(png,make([]byte,len(png))) {
        t.Fatal("discard must clear in-memory handwriting")
    }
    session.discardCapture()
}
