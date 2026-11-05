package main

import (
 "context"
 "crypto/ed25519"
 "crypto/rand"
 "os"
 "path/filepath"
 "testing"
 "time"
)

type fixedBackendPreviewResolver struct { state authoritativeWacomPreviewState }
func (r fixedBackendPreviewResolver) ResolveAuthorizedPreview(_ context.Context,_ string)(authoritativeWacomPreviewState,error) {
 return r.state,nil
}
func TestVerifiedAuthorityRequiresLocallyPinnedExecutable(t *testing.T){
 pub,priv,err:=ed25519.GenerateKey(rand.Reader);if err!=nil{t.Fatal(err)}
 now:=time.Now().UTC().Truncate(time.Second)
 scope:=testPreviewScope()
 token:=previewTestToken(t,priv,now,scope)
 sdk:=filepath.Join(t.TempDir(),"approved-sdk")
 if err:=os.WriteFile(sdk,[]byte("#!/bin/sh\nexit 0\n"),0700);err!=nil{t.Fatal(err)}
 state:=authoritativeWacomPreviewState{
  Scope:scope,SessionKey:"server-session",FieldID:"borrower_signature",
  Calibration:deviceCalibration{MinX:0,MaxX:10800,MinY:0,MaxY:6480,MaxPressure:1023},
  SDKExecutable:sdk,
  Admission:previewAdmissionDependencies{
   Keys:map[string]ed25519.PublicKey{"test-ed25519-key":pub},
   Enrollment:&testEnrolledWorkstation{id:scope.WorkstationID},
   Session:&testLivePreviewSession{},
   Replay:&fakePreviewReplay{used:map[string]bool{}},
  },
 }
 authorized:=verifiedWacomWebSocketAuthority{Resolver:fixedBackendPreviewResolver{state},TrustedSDKExecutable:sdk}
 result,err:=authorized.AuthorizeWebSocketPreview(context.Background(),token)
 if err!=nil{t.Fatalf("trusted state rejected: %v",err)}
 source,ok:=result.Config.Source.(wacomSDKPreviewSource)
 if !ok||source.Executable!=sdk{t.Fatal("unapproved capture source returned")}
 if result.FieldID!="borrower_signature"||result.SessionKey!="server-session"{t.Fatal("incorrect field binding")}
 // The authority verifies without spending the one-use ticket. The
 // admission coordinator must consume it atomically after final checks.
 if len(state.Admission.Replay.(*fakePreviewReplay).used)!=0{t.Fatal("ticket consumed prematurely")}
 for _,untrusted:=range []string{"",filepath.Join(t.TempDir(),"other-sdk"),sdk+"/../approved-sdk"}{
  denied:=verifiedWacomWebSocketAuthority{Resolver:fixedBackendPreviewResolver{state},TrustedSDKExecutable:untrusted}
  if _,err:=denied.AuthorizeWebSocketPreview(context.Background(),token);err==nil{
   t.Fatalf("accepted unpinned SDK path %q",untrusted)
  }
 }
 state.SDKExecutable="/tmp/forged-sdk"
 if _,err:=(verifiedWacomWebSocketAuthority{Resolver:fixedBackendPreviewResolver{state},TrustedSDKExecutable:sdk}).AuthorizeWebSocketPreview(context.Background(),token);err==nil{
  t.Fatal("accepted server-selected alternative executable")
 }
}
func TestVerifiedAuthorityRejectsMismatchedContractHash(t *testing.T){
 pub,priv,err:=ed25519.GenerateKey(rand.Reader);if err!=nil{t.Fatal(err)}
 now:=time.Now().UTC().Truncate(time.Second)
 scope:=testPreviewScope()
 token:=previewTestToken(t,priv,now,scope)
 sdk:=filepath.Join(t.TempDir(),"sdk")
 if err:=os.WriteFile(sdk,[]byte("#!/bin/sh\nexit 0\n"),0700);err!=nil{t.Fatal(err)}
 wrong:=scope
 wrong.ContractHash="bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
 state:=authoritativeWacomPreviewState{Scope:wrong,SessionKey:"s",FieldID:"signature",SDKExecutable:sdk,
 Calibration:deviceCalibration{MinX:0,MaxX:10800,MinY:0,MaxY:6480,MaxPressure:1023},
 Admission:previewAdmissionDependencies{Keys:map[string]ed25519.PublicKey{"test-ed25519-key":pub},
 Session:&testLivePreviewSession{},Enrollment:&testEnrolledWorkstation{id:scope.WorkstationID},
 Replay:&fakePreviewReplay{used:map[string]bool{}}}}
 authority:=verifiedWacomWebSocketAuthority{Resolver:fixedBackendPreviewResolver{state},TrustedSDKExecutable:sdk}
 if _,err:=authority.AuthorizeWebSocketPreview(context.Background(),token);err==nil{t.Fatal("mismatched contract accepted")}
}
