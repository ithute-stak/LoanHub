package main

import (
 "context"
 "errors"
 "testing"
)

func TestBackendLiveAuthorityRechecksEveryCall(t *testing.T){
 ticket,resolver,provider:=makeResolverFixture(t)
 state,err:=resolver.ResolveAuthorizedPreview(context.Background(),ticket)
 if err!=nil{t.Fatal(err)}
 live,ok:=state.Admission.Session.(*backendLivePreviewAuthority)
 if !ok{t.Fatal("no backend-bound revocation authority")}
 before:=provider.calls
 if err=live.CheckPreviewActive(state.Scope);err!=nil{t.Fatal(err)}
 id,err:=live.AuthenticatedWorkstationID()
 if err!=nil||id!=state.Scope.WorkstationID{t.Fatal("workstation not revalidated")}
 if provider.calls<before+2{t.Fatal("revocation checks were cached")}
 provider.snapshot.ContractHash="bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
 if err=live.CheckPreviewActive(state.Scope);err==nil{t.Fatal("changed contract not revoked")}
}
func TestBackendLiveAuthorityRefusesUnavailableBackend(t *testing.T){
 ticket,resolver,provider:=makeResolverFixture(t)
 state,err:=resolver.ResolveAuthorizedPreview(context.Background(),ticket)
 if err!=nil{t.Fatal(err)}
 live:=state.Admission.Session.(*backendLivePreviewAuthority)
 provider.err=errors.New("disconnected")
 if err:=live.CheckPreviewActive(state.Scope);err==nil{t.Fatal("offline backend allowed preview")}
 if _,err:=live.AuthenticatedWorkstationID();err==nil{t.Fatal("offline backend allowed workstation")}
}
func TestBackendLiveAuthorityRejectsDifferentScope(t *testing.T){
 ticket,resolver,_:=makeResolverFixture(t)
 state,err:=resolver.ResolveAuthorizedPreview(context.Background(),ticket)
 if err!=nil{t.Fatal(err)}
 live:=state.Admission.Session.(*backendLivePreviewAuthority)
 other:=state.Scope
 other.OperatorID="88888888-8888-8888-8888-888888888888"
 if err:=live.CheckPreviewActive(other);err==nil{t.Fatal("different operator admitted")}
}
