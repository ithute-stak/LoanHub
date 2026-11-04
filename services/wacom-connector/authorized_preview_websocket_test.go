package main

import (
 "context"
 "errors"
 "net/http"
 "net/http/httptest"
 "testing"
)

type rejectingWacomWSAuthority struct{ calls int }
func (a *rejectingWacomWSAuthority) AuthorizeWebSocketPreview(_ context.Context,_ string)(approvedWacomWebSocketPreview,error) {
 a.calls++
 return approvedWacomWebSocketPreview{},errors.New("denied")
}

func TestWacomWSRejectsUntrustedOriginsBeforeUpgrade(t *testing.T){
 authority:=&rejectingWacomWSAuthority{}
 h:=newLocalWacomWSServer(authority)
 for _,origin:=range []string{"","https://attacker.invalid","http://loanhub.co.ls","https://loanhub.co.ls.attacker.invalid"} {
  r:=httptest.NewRequest(http.MethodGet,"http://127.0.0.1:8765/v1/preview/stream",nil)
  if origin!="" {r.Header.Set("Origin",origin)}
  w:=httptest.NewRecorder()
  h.ServeHTTP(w,r)
  if w.Code!=http.StatusForbidden {t.Fatalf("origin %q: status=%d",origin,w.Code)}
 }
 if authority.calls!=0{t.Fatal("untrusted request reached authorizer")}
}
func TestWacomWSRefusesUnconfiguredAuthority(t *testing.T){
 h:=newLocalWacomWSServer(nil)
 r:=httptest.NewRequest(http.MethodGet,"http://127.0.0.1:8765/v1/preview/stream",nil)
 r.Header.Set("Origin","https://loanhub.co.ls")
 w:=httptest.NewRecorder()
 h.ServeHTTP(w,r)
 if w.Code!=http.StatusServiceUnavailable {t.Fatalf("expected disabled, got %d",w.Code)}
}
func TestWacomWSRejectsWrongHostOrPath(t *testing.T){
 h:=newLocalWacomWSServer(&rejectingWacomWSAuthority{})
 for _,path:=range []string{"/v1/preview/stream?ticket=secret","/v1/device/status"}{
  r:=httptest.NewRequest(http.MethodGet,"http://127.0.0.1:8765"+path,nil)
  r.Header.Set("Origin","https://loanhub.co.ls")
  w:=httptest.NewRecorder();h.ServeHTTP(w,r)
  if w.Code!=http.StatusForbidden{t.Fatalf("path %q accepted: %d",path,w.Code)}
 }
 r:=httptest.NewRequest(http.MethodGet,"http://localhost:8765/v1/preview/stream",nil)
 r.Header.Set("Origin","https://loanhub.co.ls")
 w:=httptest.NewRecorder();h.ServeHTTP(w,r)
 if w.Code!=http.StatusForbidden{t.Fatalf("host not pinned: %d",w.Code)}
}
func TestWacomWSDeviceGateSingleCapture(t *testing.T){
 h:=newLocalWacomWSServer(&rejectingWacomWSAuthority{})
 if !h.acquire(){t.Fatal("failed to acquire capture gate")}
 if h.acquire(){t.Fatal("second concurrent capture admitted")}
 h.release()
 if !h.acquire(){t.Fatal("capture gate not released")}
 h.release()
}
