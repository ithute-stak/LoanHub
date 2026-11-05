package main

import (
 "context"
 "crypto/ed25519"
 "crypto/rand"
 "errors"
 "testing"
 "time"
)

type fixedPreviewSnapshotProvider struct {
 snapshot backendWacomPreviewSnapshot
 err error
 calls int
}
func(s *fixedPreviewSnapshotProvider) FetchPreviewSnapshot(ctx context.Context,_ string)(backendWacomPreviewSnapshot,error){
 s.calls++
 if err:=ctx.Err();err!=nil{return backendWacomPreviewSnapshot{},err}
 return s.snapshot,s.err
}
func makeResolverFixture(t *testing.T)(string,mtlsWacomPreviewResolver,*fixedPreviewSnapshotProvider){
 t.Helper()
 pub,priv,err:=ed25519.GenerateKey(rand.Reader)
 if err!=nil{t.Fatal(err)}
 scope:=testPreviewScope()
 token:=previewTestToken(t,priv,time.Now().UTC().Truncate(time.Second),scope)
 snapshot:=backendWacomPreviewSnapshot{
  CompanyID:scope.CompanyID,OperatorID:scope.OperatorID,
  ContractID:scope.ContractID,ContractHash:scope.ContractHash,
  SessionID:scope.SessionID,WorkstationID:scope.WorkstationID,
  SessionKey:scope.SessionID,FieldID:"borrower_signature",
 }
 backend:=&fixedPreviewSnapshotProvider{snapshot:snapshot}
 resolver:=mtlsWacomPreviewResolver{
  Backend:backend,TrustedWorkstationID:scope.WorkstationID,
  TrustedSDKExecutable:"/usr/local/libexec/wacom/simpleInterface",
  Keys:map[string]ed25519.PublicKey{"test-ed25519-key":pub},
  Replay:&fakePreviewReplay{used:map[string]bool{}},
  Calibration:deviceCalibration{MinX:0,MaxX:10800,MinY:0,MaxY:6480,MaxPressure:1023},
 }
 return token,resolver,backend
}
func TestWacomMTLSResolverRequiresExactBackendScope(t *testing.T){
 token,resolver,backend:=makeResolverFixture(t)
 out,err:=resolver.ResolveAuthorizedPreview(context.Background(),token)
 if err!=nil{t.Fatal(err)}
 if out.Scope.WorkstationID!=resolver.TrustedWorkstationID||
   out.SDKExecutable!=resolver.TrustedSDKExecutable||
   out.SessionKey!=backend.snapshot.SessionID||
   out.FieldID!="borrower_signature" {t.Fatal("resolver lost trusted scope")}
 for _,mutate:=range []func(*backendWacomPreviewSnapshot){
  func(s *backendWacomPreviewSnapshot){s.WorkstationID="77777777-7777-7777-7777-777777777777"},
  func(s *backendWacomPreviewSnapshot){s.ContractHash="bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"},
  func(s *backendWacomPreviewSnapshot){s.FieldID="guarantor_signature"},
  func(s *backendWacomPreviewSnapshot){s.SessionKey="untrusted"},
  func(s *backendWacomPreviewSnapshot){s.CompanyID="invalid"},
 } {
  original:=backend.snapshot
  mutate(&backend.snapshot)
  if _,err:=resolver.ResolveAuthorizedPreview(context.Background(),token);err==nil{
   t.Fatal("accepted backend response with a mismatched field or scope")
  }
  backend.snapshot=original
 }
}
func TestWacomMTLSResolverFailsClosedWithoutTrustDependencies(t *testing.T){
 token,resolver,backend:=makeResolverFixture(t)
 resolver.Replay=nil
 if _,err:=resolver.ResolveAuthorizedPreview(context.Background(),token);err==nil{t.Fatal("missing replay store accepted")}
 resolver.Replay=&fakePreviewReplay{used:map[string]bool{}}
 backend.err=errors.New("backend offline")
 if _,err:=resolver.ResolveAuthorizedPreview(context.Background(),token);err==nil{t.Fatal("unavailable backend accepted")}
}
func TestWacomMTLSResolverCancelledRequestCannotQueryBackend(t *testing.T){
 token,resolver,backend:=makeResolverFixture(t)
 ctx,cancel:=context.WithCancel(context.Background());cancel()
 if _,err:=resolver.ResolveAuthorizedPreview(ctx,token);err==nil{t.Fatal("cancelled request accepted")}
 if backend.calls!=0{t.Fatal("backend consulted after cancellation")}
}
