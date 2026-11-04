package main

import (
 "crypto/ed25519"
 "os"
 "path/filepath"
 "testing"
)

func TestWorkstationIdentityInitializationAndNoOverwrite(t *testing.T) {
 dir:=filepath.Join(t.TempDir(),"wacom-private")
 if err:=os.Mkdir(dir,0700);err!=nil {t.Fatal(err)}
 registration,err:=initializeWorkstationIdentity(dir)
 if err!=nil {t.Fatal(err)}
 if !validUUID(registration.WorkstationID) {t.Fatal("invalid UUID")}
 info,err:=os.Lstat(filepath.Join(dir,workstationIdentityFilename))
 if err!=nil {t.Fatal(err)}
 if info.Mode().Perm()!=0600 {t.Fatalf("identity must be private: %v",info.Mode().Perm())}
 id,priv,err:=loadWorkstationIdentity(dir)
 if err!=nil {t.Fatal(err)}
 if id!=registration.WorkstationID||len(priv)!=ed25519.PrivateKeySize {t.Fatal("identity mismatch")}
 if _,err:=initializeWorkstationIdentity(dir);err==nil {t.Fatal("existing identity overwritten")}
 after,_,err:=loadWorkstationIdentity(dir)
 if err!=nil||after!=id {t.Fatal("reprovisioning changed persistent identity")}
}

func TestWorkstationIdentityRejectsUnsafeDirectoriesAndFiles(t *testing.T) {
 root:=t.TempDir()
 dir:=filepath.Join(root,"owned")
 if err:=os.Mkdir(dir,0700);err!=nil {t.Fatal(err)}
 alias:=filepath.Join(root,"alias")
 if err:=os.Symlink(dir,alias);err!=nil {t.Fatal(err)}
 if _,err:=initializeWorkstationIdentity(alias);err==nil {t.Fatal("symlink accepted")}
 if _,err:=initializeWorkstationIdentity("relative/path");err==nil {t.Fatal("relative directory accepted")}
 if err:=os.Chmod(dir,0777);err!=nil {t.Fatal(err)}
 if _,err:=initializeWorkstationIdentity(dir);err==nil {t.Fatal("insecure directory accepted")}
 if err:=os.Chmod(dir,0700);err!=nil {t.Fatal(err)}
 if _,err:=initializeWorkstationIdentity(dir);err!=nil {t.Fatal(err)}
 path:=filepath.Join(dir,workstationIdentityFilename)
 if err:=os.Chmod(path,0644);err!=nil {t.Fatal(err)}
 if _,_,err:=loadWorkstationIdentity(dir);err==nil {t.Fatal("world readable secret accepted")}
}

func TestWorkstationIdentityNeverPrintsSecretInPublicRegistration(t *testing.T) {
 dir:=filepath.Join(t.TempDir(),"owned")
 if err:=os.Mkdir(dir,0700);err!=nil {t.Fatal(err)}
 public,err:=initializeWorkstationIdentity(dir)
 if err!=nil {t.Fatal(err)}
 secret,err:=os.ReadFile(filepath.Join(dir,workstationIdentityFilename))
 if err!=nil {t.Fatal(err)}
 if len(secret)==0||len(public.PublicKeyBase64)!=44 {t.Fatal("wrong provisioning format")}
 if public.WorkstationID==""||public.PublicKeyBase64=="" {t.Fatal("missing public registration fields")}
}
