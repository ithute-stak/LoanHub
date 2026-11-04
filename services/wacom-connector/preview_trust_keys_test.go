package main

import (
    "crypto/ed25519"
    "crypto/rand"
    "encoding/base64"
    "encoding/json"
    "os"
    "path/filepath"
    "testing"
)

func trustBundle(t *testing.T, dir string, key ed25519.PublicKey) string {
    t.Helper()
    path := filepath.Join(dir, "trusted-preview-keys.json")
    doc := map[string]any{
        "version": 1,
        "keys": []map[string]any{{
            "id": "trusted-backend-key-1",
            "public_key_base64": base64.StdEncoding.EncodeToString(key),
        }},
    }
    raw, err := json.Marshal(doc)
    if err != nil { t.Fatal(err) }
    if err := os.WriteFile(path,raw,0600); err != nil { t.Fatal(err) }
    return path
}
func TestPinnedPublicKeyLoaderValidAndRejectsWrongKey(t *testing.T) {
    dir := filepath.Join(t.TempDir(), "trusted")
    if err := os.Mkdir(dir,0700); err != nil { t.Fatal(err) }
    pub,priv,err := ed25519.GenerateKey(rand.Reader)
    if err != nil { t.Fatal(err) }
    path := trustBundle(t,dir,pub)
    keys,err := loadPinnedWacomPreviewKeys(path)
    if err != nil { t.Fatal(err) }
    if len(keys)!=1 || len(keys["trusted-backend-key-1"])!=ed25519.PublicKeySize {
        t.Fatalf("invalid trusted key bundle: %d",len(keys))
    }
    msg:=[]byte("authenticated preview ticket")
    signed:=ed25519.Sign(priv,msg)
    if !ed25519.Verify(keys["trusted-backend-key-1"],msg,signed) { t.Fatal("pinned key did not verify") }
    other,_,_ := ed25519.GenerateKey(rand.Reader)
    if ed25519.Verify(other,msg,signed) { t.Fatal("wrong key verified") }
}
func TestPinnedKeyLoaderRejectsUnsafeFileAndDirectory(t *testing.T) {
    root := t.TempDir()
    dir := filepath.Join(root,"trusted")
    if err:=os.Mkdir(dir,0700);err!=nil {t.Fatal(err)}
    pub,_,_ := ed25519.GenerateKey(rand.Reader)
    path:=trustBundle(t,dir,pub)
    symlink:=filepath.Join(dir,"redirect.json")
    if err:=os.Symlink(path,symlink);err!=nil {t.Fatal(err)}
    if _,err:=loadPinnedWacomPreviewKeys(symlink);err==nil {t.Fatal("symlink accepted")}
    if err:=os.Chmod(path,0644);err!=nil {t.Fatal(err)}
    if _,err:=loadPinnedWacomPreviewKeys(path);err==nil {t.Fatal("world-readable key bundle accepted")}
    if err:=os.Chmod(path,0600);err!=nil {t.Fatal(err)}
    if err:=os.Chmod(dir,0755);err!=nil {t.Fatal(err)}
    if _,err:=loadPinnedWacomPreviewKeys(path);err==nil {t.Fatal("public directory accepted")}
}
func TestPinnedKeyLoaderRejectsInvalidAndDuplicateRecords(t *testing.T) {
    dir := filepath.Join(t.TempDir(),"trusted")
    if err:=os.Mkdir(dir,0700);err!=nil {t.Fatal(err)}
    pub,_,_ := ed25519.GenerateKey(rand.Reader)
    path:=trustBundle(t,dir,pub)
    for _,doc:=range []string{
        `{"version":2,"keys":[{"id":"first","public_key_base64":"AA=="}]}`,
        `{"version":1,"keys":[]}`,
        `{"version":1,"keys":[{"id":"../../unsafe","public_key_base64":"AA=="}]}`,
        `{"version":1,"keys":[{"id":"first","public_key_base64":"AA=="}]}`,
        `{"version":1,"keys":[],"unexpected":"ignored"}`,
    } {
        if err:=os.WriteFile(path,[]byte(doc),0600);err!=nil {t.Fatal(err)}
        if _,err:=loadPinnedWacomPreviewKeys(path);err==nil {
            t.Errorf("unsafe trust document accepted: %s",doc)
        }
    }
    value:=base64.StdEncoding.EncodeToString(pub)
    duplicate:=`{"version":1,"keys":[{"id":"same","public_key_base64":"`+value+`"},{"id":"same","public_key_base64":"`+value+`"}]}`
    if err:=os.WriteFile(path,[]byte(duplicate),0600);err!=nil {t.Fatal(err)}
    if _,err:=loadPinnedWacomPreviewKeys(path);err==nil {t.Fatal("duplicate key id accepted")}
}
