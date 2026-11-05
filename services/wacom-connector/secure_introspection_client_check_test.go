package main

import (
 "crypto/tls"
 "net/http"
 "testing"
 "time"
)

func TestProtectedPreviewRejectsInsecureBackendTransport(t *testing.T){
 cfg:=protectedFactoryConfig(t)
 if !cfg.Backend.securelyConfigured(){t.Fatal("valid pinned mTLS transport rejected")}
 cfg.Backend.client.Transport.(*http.Transport).TLSClientConfig.InsecureSkipVerify=true
 if _,err:=newProtectedWacomPreviewAuthority(cfg);err==nil{
  t.Fatal("insecure TLS verification admitted")
 }
 cfg=protectedFactoryConfig(t)
 cfg.Backend.client.Transport.(*http.Transport).TLSClientConfig.MinVersion=tls.VersionTLS12
 if _,err:=newProtectedWacomPreviewAuthority(cfg);err==nil{
  t.Fatal("TLS 1.2 minimum admitted")
 }
 cfg=protectedFactoryConfig(t)
 cfg.Backend.client.Transport.(*http.Transport).TLSClientConfig.Certificates=nil
 if _,err:=newProtectedWacomPreviewAuthority(cfg);err==nil{
  t.Fatal("missing client certificate admitted")
 }
 cfg=protectedFactoryConfig(t)
 cfg.Backend.client.Transport.(*http.Transport).TLSClientConfig.RootCAs=nil
 if _,err:=newProtectedWacomPreviewAuthority(cfg);err==nil{
  t.Fatal("missing server CA pin admitted")
 }
 cfg=protectedFactoryConfig(t)
 cfg.Backend.client.Transport=http.DefaultTransport
 if _,err:=newProtectedWacomPreviewAuthority(cfg);err==nil{
  t.Fatal("default non-mTLS transport admitted")
 }
 cfg=protectedFactoryConfig(t)
 cfg.Backend.endpoint="https://evil.example"+wacomIntrospectionPath
 if _,err:=newProtectedWacomPreviewAuthority(cfg);err==nil{
  t.Fatal("off-domain introspection endpoint admitted")
 }
 cfg=protectedFactoryConfig(t)
 cfg.Backend.client.Timeout=20*time.Second
 if _,err:=newProtectedWacomPreviewAuthority(cfg);err==nil{
  t.Fatal("unbounded introspection timeout admitted")
 }
}
