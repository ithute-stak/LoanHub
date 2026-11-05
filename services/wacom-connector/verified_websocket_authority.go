package main

// Backend-bound adapter for the Wacom WebSocket preview endpoint.
// This is NOT a backend client: a separately authenticated resolver must
// obtain current enrollment, session, field and contract hash from LoanHub,
// never from browser parameters or unverified token claims.
import (
 "context"
 "errors"
 "time"
)

type authoritativeWacomPreviewState struct {
 Scope previewTicketScope
 SessionKey string
 FieldID string
 Admission previewAdmissionDependencies
 Calibration deviceCalibration
 SDKExecutable string
}

type backendWacomPreviewResolver interface {
 // ResolveAuthorizedPreview must use a mutually authenticated connection
 // and fetch authoritative, current backend state. Ticket contents are
 // untrusted until checked with pinned signer keys below.
 ResolveAuthorizedPreview(ctx context.Context, ticket string) (authoritativeWacomPreviewState,error)
}

type verifiedWacomWebSocketAuthority struct {
 Resolver backendWacomPreviewResolver
}

func(a verifiedWacomWebSocketAuthority) AuthorizeWebSocketPreview(
 ctx context.Context,ticket string,
)(approvedWacomWebSocketPreview,error){
 var denied=errors.New("Wacom backend preview authorization unavailable")
 if ctx==nil||ctx.Err()!=nil||a.Resolver==nil||len(ticket)<64||len(ticket)>3500{return approvedWacomWebSocketPreview{},denied}
 state,err:=a.Resolver.ResolveAuthorizedPreview(ctx,ticket)
 if err!=nil||ctx.Err()!=nil{return approvedWacomWebSocketPreview{},denied}
 if state.SessionKey==""||len(state.SessionKey)>256||
  state.FieldID==""||len(state.FieldID)>128||
  !state.Calibration.valid()||state.SDKExecutable==""||
  len(state.Admission.Keys)==0||state.Admission.Session==nil||
  state.Admission.Enrollment==nil||state.Admission.Replay==nil{
  return approvedWacomWebSocketPreview{},denied
 }
 // Signature and exact trusted backend scope are checked before SDK
 // admission. Atomic single-use consume occurs in the coordinator, not here.
 now:=time.Now().UTC()
 if _,err=verifyPreviewTicketSignatureAndScope(ticket,state.Admission.Keys,state.Scope,now);err!=nil{
  return approvedWacomWebSocketPreview{},denied
 }
 if err=state.Admission.Session.CheckPreviewActive(state.Scope);err!=nil{
  return approvedWacomWebSocketPreview{},denied
 }
 id,err:=state.Admission.Enrollment.AuthenticatedWorkstationID()
 if err!=nil||id!=state.Scope.WorkstationID{return approvedWacomWebSocketPreview{},denied}
 return approvedWacomWebSocketPreview{
  Scope:state.Scope,FieldID:state.FieldID,SessionKey:state.SessionKey,
  Config:authorizedPreviewConfig{
   Admission:state.Admission,Calibration:state.Calibration,
   Source:wacomSDKPreviewSource{Executable:state.SDKExecutable},
   MaxDuration:12*time.Second,
  },
 },nil
}
