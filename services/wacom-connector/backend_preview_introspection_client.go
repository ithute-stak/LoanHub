package main

// Restricted HTTPS client for retrieving the currently authorized contract,
// operator, field, and workstation state. The endpoint is connector-only and
// must be separately implemented with verified client-certificate identity.
// Do not use an operator's bearer token or trust browser-supplied session IDs.
import (
 "bytes"
 "context"
 "crypto/tls"
 "crypto/x509"
 "encoding/json"
 "errors"
 "io"
 "net/http"
 "net/url"
 "strings"
 "time"
)

const wacomIntrospectionPath="/api/v1/wacom/connector/preview-introspect"
const maxIntrospectionResponse=16*1024

type backendWacomPreviewSnapshot struct {
 CompanyID string `json:"company_id"`
 OperatorID string `json:"operator_id"`
 ContractID string `json:"contract_id"`
 ContractHash string `json:"contract_hash"`
 SessionID string `json:"session_id"`
 WorkstationID string `json:"workstation_id"`
 SessionKey string `json:"session_key"`
 FieldID string `json:"field_id"`
 SDKExecutable string `json:"sdk_executable"`
}

// HardenedWacomIntrospectionClient only fetches backend-asserted scope.
// It does not manufacture enrollment, replay, signing keys or revocation
// services: those must be separately bound to the trusted backend.
type hardenedWacomIntrospectionClient struct {
 client *http.Client
 endpoint string
}

func newHardenedWacomIntrospectionClient(
 endpoint string,
 rootPEM []byte,
 deviceCert tls.Certificate,
)(*hardenedWacomIntrospectionClient,error){
 u,err:=url.Parse(endpoint)
 if err!=nil||u.Scheme!="https"||u.Host!="loanhub.co.ls"||
  u.Path!=wacomIntrospectionPath||u.RawQuery!=""||u.Fragment!=""||
  u.User!=nil||u.Opaque!=""||len(rootPEM)==0||len(deviceCert.Certificate)==0||
  deviceCert.PrivateKey==nil{
  return nil,errors.New("trusted Wacom introspection endpoint not configured")
 }
 roots:=x509.NewCertPool()
 if !roots.AppendCertsFromPEM(rootPEM){return nil,errors.New("trusted Wacom CA unavailable")}
 transport:=&http.Transport{
  TLSClientConfig:&tls.Config{MinVersion:tls.VersionTLS13,RootCAs:roots,
   Certificates:[]tls.Certificate{deviceCert},ServerName:"loanhub.co.ls"},
  DisableKeepAlives:true,
  MaxIdleConns:0,
  ResponseHeaderTimeout:2*time.Second,
 }
 return &hardenedWacomIntrospectionClient{
  endpoint:u.String(),
  client:&http.Client{Transport:transport,Timeout:4*time.Second,
   CheckRedirect:func(_ *http.Request,_ []*http.Request)error{
    return errors.New("Wacom introspection redirects forbidden")
   }},
 },nil
}

func(c *hardenedWacomIntrospectionClient) FetchPreviewSnapshot(
 ctx context.Context, ticket string,
)(backendWacomPreviewSnapshot,error){
 denied:=errors.New("Wacom backend introspection unavailable")
 if c==nil||c.client==nil||ctx==nil||ctx.Err()!=nil||
  len(ticket)<64||len(ticket)>3500{return backendWacomPreviewSnapshot{},denied}
 // Never place the bearer ticket in a URL, header, log or cookie.
 payload,err:=json.Marshal(struct{Ticket string `json:"preview_ticket"`}{ticket})
 if err!=nil{return backendWacomPreviewSnapshot{},denied}
 req,err:=http.NewRequestWithContext(ctx,http.MethodPost,c.endpoint,bytes.NewReader(payload))
 if err!=nil{return backendWacomPreviewSnapshot{},denied}
 req.Header.Set("Content-Type","application/json")
 req.Header.Set("Accept","application/json")
 req.Header.Set("Cache-Control","no-store")
 resp,err:=c.client.Do(req)
 if err!=nil{return backendWacomPreviewSnapshot{},denied}
 defer resp.Body.Close()
 if resp.StatusCode!=http.StatusOK||
  !strings.HasPrefix(resp.Header.Get("Content-Type"),"application/json"){
  return backendWacomPreviewSnapshot{},denied
 }
 var snapshot backendWacomPreviewSnapshot
 decoder:=json.NewDecoder(io.LimitReader(resp.Body,maxIntrospectionResponse+1))
 decoder.DisallowUnknownFields()
 if err=decoder.Decode(&snapshot);err!=nil{return backendWacomPreviewSnapshot{},denied}
 var tail any
 if err=decoder.Decode(&tail);err!=io.EOF{return backendWacomPreviewSnapshot{},denied}
 if snapshot.CompanyID==""||snapshot.OperatorID==""||snapshot.ContractID==""||
  snapshot.SessionID==""||snapshot.WorkstationID==""||
  !isLowerHexSHA256(snapshot.ContractHash)||snapshot.SessionKey==""||
  snapshot.FieldID==""||snapshot.SDKExecutable==""{
  return backendWacomPreviewSnapshot{},denied
 }
 return snapshot,nil
}
