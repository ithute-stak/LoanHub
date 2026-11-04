package main

import (
 "context"
 "errors"
 "net/http"
 "net/http/httptest"
 "strings"
 "testing"
)
type refusingPreviewAuthority struct {calls int}
func (a *refusingPreviewAuthority) AuthorizeCapture(_ context.Context,_ string)(previewTicketScope,authorizedPreviewConfig,error){
 a.calls++
 return previewTicketScope{},authorizedPreviewConfig{},errors.New("denied")
}
func previewRequest(method,origin,body string)*http.Request {
 r:=httptest.NewRequest(method,"http://127.0.0.1:8765"+previewPath,strings.NewReader(body))
 if origin!="" {r.Header.Set("Origin",origin)}
 r.Header.Set("Content-Type","application/json")
 return r
}
func TestPreviewHTTPFailsClosedWithoutConfiguredAuthority(t *testing.T){
 handler:=newAuthorizedPreviewHTTPHandler(nil)
 token:=strings.Repeat("a",100)
 r:=previewRequest("POST","https://loanhub.co.ls",`{"preview_ticket":"`+token+`"}`)
 w:=httptest.NewRecorder();handler.ServeHTTP(w,r)
 if w.Code!=http.StatusServiceUnavailable {t.Fatalf("expected disabled response, got %d",w.Code)}
 if strings.Contains(w.Body.String(),token) {t.Fatal("ticket leaked")}
}
func TestPreviewHTTPRejectsUntrustedOriginsBeforeAuthorization(t *testing.T){
 authority:=&refusingPreviewAuthority{}
 handler:=newAuthorizedPreviewHTTPHandler(authority)
 for _, origin:=range []string{"","https://evil.example","http://loanhub.co.ls","https://loanhub.co.ls.evil.example"} {
  r:=previewRequest("POST",origin,`{"preview_ticket":"`+strings.Repeat("a",100)+`"}`)
  w:=httptest.NewRecorder();handler.ServeHTTP(w,r)
  if w.Code!=http.StatusForbidden {t.Fatalf("origin %q: %d",origin,w.Code)}
 }
 if authority.calls!=0 {t.Fatal("untrusted origin reached authorizer")}
}
func TestPreviewHTTPRequiresProofBeforeSDK(t *testing.T){
 authority:=&refusingPreviewAuthority{}
 handler:=newAuthorizedPreviewHTTPHandler(authority)
 r:=previewRequest("POST","https://loanhub.co.ls",`{"preview_ticket":"`+strings.Repeat("a",100)+`"}`)
 w:=httptest.NewRecorder();handler.ServeHTTP(w,r)
 if w.Code!=http.StatusForbidden || authority.calls!=1 {t.Fatalf("expected authority denial, got %d, calls=%d",w.Code,authority.calls)}
}
func TestPreviewHTTPRejectsClientSuppliedScope(t *testing.T){
 authority:=&refusingPreviewAuthority{}
 handler:=newAuthorizedPreviewHTTPHandler(authority)
 r:=previewRequest("POST","https://loanhub.co.ls",`{"preview_ticket":"`+strings.Repeat("a",100)+`","company_id":"forged"}`)
 w:=httptest.NewRecorder();handler.ServeHTTP(w,r)
 if w.Code!=http.StatusBadRequest || authority.calls!=0 {t.Fatalf("untrusted fields admitted: %d calls=%d",w.Code,authority.calls)}
}
func TestPreviewHTTPPreflightAndHostRestrictions(t *testing.T){
 handler:=newAuthorizedPreviewHTTPHandler(nil)
 r:=previewRequest("OPTIONS","https://loanhub.co.ls","")
 w:=httptest.NewRecorder();handler.ServeHTTP(w,r)
 if w.Code!=http.StatusNoContent || w.Header().Get("Access-Control-Allow-Origin")!="https://loanhub.co.ls" {t.Fatalf("invalid preflight: %d",w.Code)}
 r=previewRequest("POST","https://loanhub.co.ls","{}")
 r.Host="localhost:8765"
 w=httptest.NewRecorder();handler.ServeHTTP(w,r)
 if w.Code!=http.StatusForbidden {t.Fatalf("host check failed: %d",w.Code)}
}
