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

func testProtectedMuxSetup(t *testing.T)(protectedWacomPreviewServerConfig,func()){
 t.Helper()
 directory:=filepath.Join(t.TempDir(),"workstation")
 if err:=os.Mkdir(directory,0700);err!=nil{t.Fatal(err)}
 identity,err:=initializeWorkstationIdentity(directory)
 if err!=nil{t.Fatal(err)}
 public,_,err:=ed25519.GenerateKey(rand.Reader)
 if err!=nil{t.Fatal(err)}
 kid:="test-preview-signing-key"
 keyJSON,err:=json.Marshal(map[string]string{
  "key_id":kid,"public_key_base64":base64.StdEncoding.EncodeToString(public),
 })
 if err!=nil{t.Fatal(err)}
 if err:=os.WriteFile(filepath.Join(directory,trustedPreviewBackendKeyFile),keyJSON,0600);err!=nil{t.Fatal(err)}
 authority:=protectedFactoryConfig(t)
 authority.WorkstationID=identity.WorkstationID
 authority.PinnedKeys=map[string]ed25519.PublicKey{kid:public}
 return protectedWacomPreviewServerConfig{IdentityDirectory:directory,Authority:authority},func(){}
}

func TestProtectedTestMuxFailsClosedWhenTrustOrIdentityMissing(t *testing.T){
 cfg,_:=testProtectedMuxSetup(t)
 cfg.IdentityDirectory=""
 if _,err:=newProtectedWacomPreviewTestMux(cfg);err==nil{t.Fatal("missing identity accepted")}
 cfg,_=testProtectedMuxSetup(t)
 cfg.Authority.Backend=nil
 if _,err:=newProtectedWacomPreviewTestMux(cfg);err==nil{t.Fatal("missing live mTLS client accepted")}
 cfg,_=testProtectedMuxSetup(t)
 cfg.Authority.WorkstationID="11111111-1111-4111-8111-111111111111"
 if _,err:=newProtectedWacomPreviewTestMux(cfg);err==nil{t.Fatal("wrong workstation accepted")}
 cfg,_=testProtectedMuxSetup(t)
 cfg.Authority.PinnedKeys["test-preview-signing-key"]=make([]byte,32)
 if _,err:=newProtectedWacomPreviewTestMux(cfg);err==nil{t.Fatal("substituted signer accepted")}
 cfg,_=testProtectedMuxSetup(t)
 cfg.Authority.ReplayDirectory=filepath.Join(t.TempDir(),"missing")
 if _,err:=newProtectedWacomPreviewTestMux(cfg);err==nil{t.Fatal("missing atomic replay directory accepted")}
}

func TestProtectedTestMuxCanComposeWithoutEnablingUnverifiedCapture(t *testing.T){
 cfg,_:=testProtectedMuxSetup(t)
 mux,err:=newProtectedWacomPreviewTestMux(cfg)
 if err!=nil{t.Fatal(err)}
 req:=httptest.NewRequest(http.MethodGet,"http://127.0.0.1:8765"+previewWebSocketPath,nil)
 req.Header.Set("Origin","https://evil.example")
 out:=httptest.NewRecorder()
 mux.ServeHTTP(out,req)
 if out.Code!=http.StatusForbidden{
  t.Fatalf("untrusted browser origin unexpectedly admitted: %d",out.Code)
 }
 req=httptest.NewRequest(http.MethodGet,"http://127.0.0.1:8765"+previewWebSocketPath,nil)
 req.Header.Set("Origin","https://loanhub.co.ls")
 out=httptest.NewRecorder()
 mux.ServeHTTP(out,req)
 if out.Code==http.StatusSwitchingProtocols{
  t.Fatal("WebSocket admitted without actual upgrade and authenticated ticket")
 }
}
