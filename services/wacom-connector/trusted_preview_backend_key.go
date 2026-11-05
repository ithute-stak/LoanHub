package main

// Load independently provisioned server verification key from the same
// private, owned directory as the workstation identity. Never trust an
// endpoint, browser header, or unsigned challenge to supply this key.
import (
 "crypto/ed25519"
 "encoding/base64"
 "encoding/json"
 "errors"
 "io"
 "os"
 "path/filepath"
 "regexp"
 "syscall"
)

const trustedPreviewBackendKeyFile = "backend-preview-public-key.json"
var backendKeyIDPattern=regexp.MustCompile(`^[A-Za-z0-9_-]{1,64}$`)

func loadTrustedBackendPreviewKeys(directory string)(map[string]ed25519.PublicKey,error){
 denied:=errors.New("trusted Wacom preview backend key unavailable")
 if err:=requirePrivateWorkstationDirectory(directory);err!=nil{return nil,denied}
 path:=filepath.Join(directory,trustedPreviewBackendKeyFile)
 info,err:=os.Lstat(path)
 if err!=nil{return nil,denied}
 stat,ok:=info.Sys().(*syscall.Stat_t)
 if !ok||!info.Mode().IsRegular()||info.Mode().Perm()!=0600||
  stat.Uid!=uint32(os.Geteuid())||info.Size()<=0||info.Size()>512 {
  return nil,denied
 }
 file,err:=os.OpenFile(path,os.O_RDONLY|syscall.O_NOFOLLOW,0)
 if err!=nil{return nil,denied}
 defer file.Close()
 opened,err:=file.Stat()
 if err!=nil||!os.SameFile(info,opened){return nil,denied}
 var payload struct{
  KeyID string `json:"key_id"`
  PublicKeyBase64 string `json:"public_key_base64"`
 }
 dec:=json.NewDecoder(io.LimitReader(file,513))
 dec.DisallowUnknownFields()
 if dec.Decode(&payload)!=nil{return nil,denied}
 var trailing any
 if dec.Decode(&trailing)!=io.EOF{return nil,denied}
 if !backendKeyIDPattern.MatchString(payload.KeyID){return nil,denied}
 public,err:=base64.StdEncoding.Strict().DecodeString(payload.PublicKeyBase64)
 if err!=nil||len(public)!=ed25519.PublicKeySize||
  base64.StdEncoding.EncodeToString(public)!=payload.PublicKeyBase64{return nil,denied}
 return map[string]ed25519.PublicKey{payload.KeyID:public},nil
}
