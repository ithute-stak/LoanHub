package main

import (
 "crypto/ed25519"
 "crypto/rand"
 "crypto/x509"
 "encoding/base64"
 "encoding/json"
 "encoding/pem"
 "os"
 "path/filepath"
 "testing"
)

func makeStagingPreflightFixture(t *testing.T)wacomStagingPreflightConfig{
 t.Helper()
 base:=t.TempDir()
 privateDir:=filepath.Join(base,"identity")
 replayDir:=filepath.Join(base,"replay")
 if err:=os.Mkdir(privateDir,0700);err!=nil{t.Fatal(err)}
 if err:=os.Mkdir(replayDir,0700);err!=nil{t.Fatal(err)}
 if _,err:=initializeWorkstationIdentity(privateDir);err!=nil{t.Fatal(err)}
 pub,_,err:=ed25519.GenerateKey(rand.Reader)
 if err!=nil{t.Fatal(err)}
 keyID:="staging-test-key"
 b64:=base64.StdEncoding.EncodeToString(pub)
 pinned,_:=json.Marshal(map[string]any{
  "version":1,"keys":[]map[string]string{{"id":keyID,"public_key_base64":b64}},
 })
 trustFile:=filepath.Join(privateDir,"preview-trust.json")
 if err:=os.WriteFile(trustFile,pinned,0600);err!=nil{t.Fatal(err)}
 backend,_:=json.Marshal(map[string]string{"key_id":keyID,"public_key_base64":b64})
 if err:=os.WriteFile(filepath.Join(privateDir,trustedPreviewBackendKeyFile),backend,0600);err!=nil{t.Fatal(err)}
 roots,client:=wacomTestTLSMaterials(t)
 caPath:=filepath.Join(privateDir,"trusted-server-ca.pem")
 certPath:=filepath.Join(privateDir,"workstation-client-cert.pem")
 keyPath:=filepath.Join(privateDir,"workstation-client-key.pem")
 if err:=os.WriteFile(caPath,roots,0600);err!=nil{t.Fatal(err)}
 if err:=os.WriteFile(certPath,pem.EncodeToMemory(&pem.Block{Type:"CERTIFICATE",Bytes:client.Certificate[0]}),0600);err!=nil{t.Fatal(err)}
 keyDER,err:=x509.MarshalPKCS8PrivateKey(client.PrivateKey)
 if err!=nil{t.Fatal(err)}
 if err:=os.WriteFile(keyPath,pem.EncodeToMemory(&pem.Block{Type:"PRIVATE KEY",Bytes:keyDER}),0600);err!=nil{t.Fatal(err)}
 sdk:=filepath.Join(base,"sdk-sample")
 if err:=os.WriteFile(sdk,[]byte("#!/bin/sh\nexit 0\n"),0700);err!=nil{t.Fatal(err)}
 return wacomStagingPreflightConfig{
  IdentityDirectory:privateDir,TrustBundlePath:trustFile,
  ReplayDirectory:replayDir,BackendCAPath:caPath,
  ClientCertificatePath:certPath,ClientKeyPath:keyPath,
  SDKExecutable:sdk,CalibrationMaxX:10800,
  CalibrationMaxY:6480,CalibrationMaxPressure:1023,
 }
}

func TestWacomStagingPreflightChecksLocalPrerequisitesOnly(t *testing.T){
 cfg:=makeStagingPreflightFixture(t)
 if err:=checkLocalWacomStagingReadiness(cfg);err!=nil{
  t.Fatalf("valid offline provisioning rejected: %v",err)
 }
 cfg.ClientKeyPath=filepath.Join(cfg.IdentityDirectory,"missing.key")
 if err:=checkLocalWacomStagingReadiness(cfg);err==nil{t.Fatal("missing client private key accepted")}
 cfg=makeStagingPreflightFixture(t)
 cfg.ReplayDirectory=filepath.Join(cfg.IdentityDirectory,"missing-replay")
 if err:=checkLocalWacomStagingReadiness(cfg);err==nil{t.Fatal("missing replay store accepted")}
 cfg=makeStagingPreflightFixture(t)
 if err:=os.Chmod(cfg.ClientKeyPath,0644);err!=nil{t.Fatal(err)}
 if err:=checkLocalWacomStagingReadiness(cfg);err==nil{t.Fatal("exposed mTLS private key accepted")}
 cfg=makeStagingPreflightFixture(t)
 cfg.CalibrationMaxX=0
 if err:=checkLocalWacomStagingReadiness(cfg);err==nil{t.Fatal("invalid SDK calibration accepted")}
 cfg=makeStagingPreflightFixture(t)
 cfg.SDKExecutable=filepath.Join(cfg.IdentityDirectory,"missing-sdk")
 if err:=checkLocalWacomStagingReadiness(cfg);err==nil{t.Fatal("missing SDK accepted")}
 cfg=makeStagingPreflightFixture(t)
 if err:=os.Remove(filepath.Join(cfg.IdentityDirectory,trustedPreviewBackendKeyFile));err!=nil{t.Fatal(err)}
 if err:=checkLocalWacomStagingReadiness(cfg);err==nil{t.Fatal("missing trusted backend key accepted")}
}

func TestStagingPreflightConfigRejectsUnsafeOrExtraKeys(t *testing.T){
 cfg:=makeStagingPreflightFixture(t)
 path:=filepath.Join(cfg.IdentityDirectory,"preflight.json")
 raw,err:=json.Marshal(cfg)
 if err!=nil{t.Fatal(err)}
 if err:=os.WriteFile(path,raw,0600);err!=nil{t.Fatal(err)}
 loaded,err:=loadWacomStagingPreflightConfig(path)
 if err!=nil{t.Fatal(err)}
 if loaded.IdentityDirectory!=cfg.IdentityDirectory{t.Fatal("configuration changed")}
 if err:=os.Chmod(path,0644);err!=nil{t.Fatal(err)}
 if _,err:=loadWacomStagingPreflightConfig(path);err==nil{t.Fatal("world-readable configuration accepted")}
 if err:=os.Chmod(path,0600);err!=nil{t.Fatal(err)}
 if err:=os.WriteFile(path,append(raw[:len(raw)-1],[]byte(`,"unexpected":true}`)...),0600);err!=nil{t.Fatal(err)}
 if _,err:=loadWacomStagingPreflightConfig(path);err==nil{t.Fatal("unknown staging config field accepted")}
}
