package main

import (
 "crypto/tls"
 "crypto/x509"
 "crypto/ed25519"
 "crypto/rand"
 "crypto/x509/pkix"
 "encoding/pem"
 "math/big"
 "testing"
 "time"
)

func wacomTestTLSMaterials(t *testing.T)([]byte,tls.Certificate){
 t.Helper()
 _,key,err:=ed25519.GenerateKey(rand.Reader)
 if err!=nil{t.Fatal(err)}
 template:=&x509.Certificate{SerialNumber:big.NewInt(99),Subject:pkix.Name{CommonName:"test-only"},
  NotBefore:time.Now().Add(-time.Hour),NotAfter:time.Now().Add(time.Hour),
  ExtKeyUsage:[]x509.ExtKeyUsage{x509.ExtKeyUsageClientAuth},
  BasicConstraintsValid:true,IsCA:true,KeyUsage:x509.KeyUsageCertSign|x509.KeyUsageDigitalSignature}
 encoded,err:=x509.CreateCertificate(rand.Reader,template,template,key.Public(),key)
 if err!=nil{t.Fatal(err)}
 root:=pem.EncodeToMemory(&pem.Block{Type:"CERTIFICATE",Bytes:encoded})
 return root,tls.Certificate{Certificate:[][]byte{encoded},PrivateKey:key}
}
func TestWacomIntrospectionRequiresPinnedMTLSAndFixedEndpoint(t *testing.T){
 root,certificate:=wacomTestTLSMaterials(t)
 valid:="https://loanhub.co.ls"+wacomIntrospectionPath
 if _,err:=newHardenedWacomIntrospectionClient(valid,root,certificate);err!=nil{t.Fatal(err)}
 for _,bad:=range []string{
  "http://loanhub.co.ls"+wacomIntrospectionPath,
  "https://evil.example"+wacomIntrospectionPath,
  "https://loanhub.co.ls.evil.example"+wacomIntrospectionPath,
  valid+"?ticket=leak",
  "https://loanhub.co.ls/wrong",
  "https://name:pass@loanhub.co.ls"+wacomIntrospectionPath,
  "https://loanhub.co.ls:443"+wacomIntrospectionPath,
 } {
  if _,err:=newHardenedWacomIntrospectionClient(bad,root,certificate);err==nil{
   t.Errorf("accepted unsafe endpoint %q",bad)
  }
 }
 if _,err:=newHardenedWacomIntrospectionClient(valid,nil,certificate);err==nil{t.Fatal("missing CA accepted")}
 if _,err:=newHardenedWacomIntrospectionClient(valid,root,tls.Certificate{});err==nil{t.Fatal("missing client certificate accepted")}
}
