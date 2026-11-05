package main

import (
 "crypto/ed25519"
 "crypto/rand"
 "os"
 "path/filepath"
 "testing"
)

func protectedFactoryConfig(t *testing.T) wacomProtectedPreviewConfig {
 t.Helper()
 pub,_,err:=ed25519.GenerateKey(rand.Reader)
 if err!=nil{t.Fatal(err)}
 dir:=filepath.Join(t.TempDir(),"replay")
 if err:=os.Mkdir(dir,0700);err!=nil{t.Fatal(err)}
 return wacomProtectedPreviewConfig{
  Backend:func()*hardenedWacomIntrospectionClient{
   root,cert:=wacomTestTLSMaterials(t)
   client,err:=newHardenedWacomIntrospectionClient(
    "https://loanhub.co.ls"+wacomIntrospectionPath,root,cert)
   if err!=nil{t.Fatal(err)}
   return client
  }(),
  WorkstationID:testPreviewScope().WorkstationID,
  SDKExecutable:"/usr/local/libexec/wacom/simpleInterface",
  ReplayDirectory:dir,
  PinnedKeys:map[string]ed25519.PublicKey{"test-ed25519-key":pub},
  Calibration:deviceCalibration{MinX:0,MaxX:10800,MinY:0,MaxY:6480,MaxPressure:1023},
 }
}
func TestProtectedFactoryUsesDurableReplayAcrossRestarts(t *testing.T){
 cfg:=protectedFactoryConfig(t)
 first,err:=newProtectedWacomPreviewAuthority(cfg)
 if err!=nil{t.Fatal(err)}
 second,err:=newProtectedWacomPreviewAuthority(cfg)
 if err!=nil{t.Fatal(err)}
 a:=first.Resolver.(mtlsWacomPreviewResolver)
 b:=second.Resolver.(mtlsWacomPreviewResolver)
 if _,ok:=a.Replay.(*filePreviewReplayStore);!ok{t.Fatal("in-memory replay used")}
 jti:="unique-test-preview-ticket-123456789"
 exp:=time.Now().Add(time.Minute).Unix()
 ok,err:=a.Replay.ConsumeOnce(jti,exp)
 if err!=nil||!ok{t.Fatalf("initial consume: %t %v",ok,err)}
 ok,err=b.Replay.ConsumeOnce(jti,exp)
 if err!=nil||ok{t.Fatalf("duplicate admitted: %t %v",ok,err)}
}
func TestProtectedFactoryRefusesUntrustedReplayDirectory(t *testing.T){
 cfg:=protectedFactoryConfig(t)
 cfg.ReplayDirectory=filepath.Join(t.TempDir(),"missing")
 if _,err:=newProtectedWacomPreviewAuthority(cfg);err==nil{t.Fatal("missing replay directory accepted")}
 cfg=protectedFactoryConfig(t)
 if err:=os.Chmod(cfg.ReplayDirectory,0777);err!=nil{t.Fatal(err)}
 if _,err:=newProtectedWacomPreviewAuthority(cfg);err==nil{t.Fatal("insecure replay directory accepted")}
}
func TestProtectedFactoryFailsClosedWithoutBackendOrSigner(t *testing.T){
 cfg:=protectedFactoryConfig(t)
 cfg.Backend=nil
 if _,err:=newProtectedWacomPreviewAuthority(cfg);err==nil{t.Fatal("missing backend accepted")}
 cfg=protectedFactoryConfig(t)
 cfg.PinnedKeys=nil
 if _,err:=newProtectedWacomPreviewAuthority(cfg);err==nil{t.Fatal("missing signer key accepted")}
}
