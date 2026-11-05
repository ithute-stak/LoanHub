package main

import (
 "crypto/ed25519"
 "crypto/rand"
 "encoding/base64"
 "encoding/json"
 "net/http"
 "net/http/httptest"
 "os"
 "path/filepath"
 "testing"
)

func TestWacomProofTestMuxRequiresProtectedIdentityAndNoCaptureRoute(t *testing.T){
 directory:=filepath.Join(t.TempDir(),"enrolled")
 if err:=os.Mkdir(directory,0700);err!=nil{t.Fatal(err)}
 if _,err:=newLocalWacomProofTestMux(directory);err==nil{
  t.Fatal("unenrolled workstation accepted")
 }
 if _,err:=initializeWorkstationIdentity(directory);err!=nil{t.Fatal(err)}
 if _,err:=newLocalWacomProofTestMux(directory);err==nil{
  t.Fatal("missing backend trust pin accepted")
 }
 public,_,err:=ed25519.GenerateKey(rand.Reader)
 if err!=nil{t.Fatal(err)}
 encoded,_:=json.Marshal(map[string]string{
  "key_id":"test-only-server",
  "public_key_base64":base64.StdEncoding.EncodeToString(public),
 })
 if err:=os.WriteFile(filepath.Join(directory,trustedPreviewBackendKeyFile),encoded,0600);err!=nil{t.Fatal(err)}
 mux,err:=newLocalWacomProofTestMux(directory)
 if err!=nil{t.Fatal(err)}
 for _,path:=range []string{"/v1/preview/stream","/v1/preview/unknown"}{
  req:=httptest.NewRequest(http.MethodGet,"http://127.0.0.1:8765"+path,nil)
  req.Header.Set("Origin","https://loanhub.co.ls")
  recorder:=httptest.NewRecorder()
  mux.ServeHTTP(recorder,req)
  if recorder.Code!=http.StatusNotFound{
   t.Fatalf("test mode unexpectedly exposed %s: %d",path,recorder.Code)
  }
 }
 req:=httptest.NewRequest(http.MethodOptions,
  "http://127.0.0.1:8765"+localWacomChallengeProofPath,nil)
 req.Header.Set("Origin","https://loanhub.co.ls")
 req.Header.Set("Access-Control-Request-Method","POST")
 req.Header.Set("Access-Control-Request-Headers","content-type")
 recorder:=httptest.NewRecorder()
 mux.ServeHTTP(recorder,req)
 if recorder.Code!=http.StatusNoContent{
  t.Fatalf("trusted proof CORS preflight rejected: %d",recorder.Code)
 }
 req=httptest.NewRequest(http.MethodOptions,
  "http://127.0.0.1:8765"+localWacomChallengeProofPath,nil)
 req.Header.Set("Origin","https://evil.example")
 req.Header.Set("Access-Control-Request-Method","POST")
 req.Header.Set("Access-Control-Request-Headers","content-type")
 recorder=httptest.NewRecorder()
 mux.ServeHTTP(recorder,req)
 if recorder.Code!=http.StatusForbidden{
  t.Fatalf("foreign origin accepted: %d",recorder.Code)
 }
}
