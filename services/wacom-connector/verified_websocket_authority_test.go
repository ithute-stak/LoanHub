package main

import (
 "context"
 "errors"
 "testing"
)
type refusedBackendWacomResolver struct {calls int}
func(r *refusedBackendWacomResolver) ResolveAuthorizedPreview(_ context.Context,_ string)(authoritativeWacomPreviewState,error){
 r.calls++
 return authoritativeWacomPreviewState{},errors.New("backend unavailable")
}
type incompleteBackendWacomResolver struct {}
func(incompleteBackendWacomResolver) ResolveAuthorizedPreview(_ context.Context,_ string)(authoritativeWacomPreviewState,error){
 return authoritativeWacomPreviewState{SessionKey:"untrusted",FieldID:"signature"},nil
}
func TestVerifiedWacomAuthorityFailsClosedWithoutBackend(t *testing.T){
 ticket:="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
 for _,authority:=range []verifiedWacomWebSocketAuthority{
  {},{Resolver:&refusedBackendWacomResolver{}},{Resolver:incompleteBackendWacomResolver{}},
 } {
  binding,err:=authority.AuthorizeWebSocketPreview(context.Background(),ticket)
  if err==nil||binding.Config.Source!=nil {t.Fatal("unauthorized capture source released")}
 }
}
func TestVerifiedWacomAuthorityRefusesCancelledContext(t *testing.T){
 resolver:=&refusedBackendWacomResolver{}
 ctx,cancel:=context.WithCancel(context.Background());cancel()
 _,err:=(verifiedWacomWebSocketAuthority{Resolver:resolver}).AuthorizeWebSocketPreview(ctx,"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")
 if err==nil||resolver.calls!=0 {t.Fatal("cancelled capture consulted backend")}
}
