package main

// Admission-time check that the backend client passed into the protected
// preview composition still has the required mTLS transport settings.
// Server-side verification remains a separate deployment prerequisite.
import (
 "crypto/tls"
 "net/http"
 "net/url"
 "time"
)

func (c *hardenedWacomIntrospectionClient) securelyConfigured() bool {
 if c==nil||c.client==nil||c.client.Transport==nil||
  c.client.Timeout<=0||c.client.Timeout>4*time.Second||
  c.client.CheckRedirect==nil{return false}
 u,err:=url.Parse(c.endpoint)
 if err!=nil||u.Scheme!="https"||u.Host!="loanhub.co.ls"||
  u.Path!=wacomIntrospectionPath||u.RawQuery!=""||u.Fragment!=""||
  u.User!=nil||u.Opaque!="" {return false}
 transport,ok:=c.client.Transport.(*http.Transport)
 if !ok||transport.TLSClientConfig==nil||
  transport.TLSClientConfig.InsecureSkipVerify||
  transport.TLSClientConfig.MinVersion!=tls.VersionTLS13||
  transport.TLSClientConfig.RootCAs==nil||
  transport.TLSClientConfig.ServerName!="loanhub.co.ls"||
  len(transport.TLSClientConfig.Certificates)!=1||
  len(transport.TLSClientConfig.Certificates[0].Certificate)==0||
  transport.TLSClientConfig.Certificates[0].PrivateKey==nil||
  !transport.DisableKeepAlives||
  transport.ResponseHeaderTimeout<=0||
  transport.ResponseHeaderTimeout>2*time.Second {
  return false
 }
 return true
}
