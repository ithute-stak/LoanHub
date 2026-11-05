package main

// Backend-backed revocation providers for preview capture. Each check makes
// a fresh authenticated mTLS introspection call. No cached snapshot or
// browser-provided identity can renew a signing session.
import (
 "context"
 "errors"
 "time"
)

const wacomRevocationRequestTimeout = 1500 * time.Millisecond

type backendLivePreviewAuthority struct {
 Backend wacomPreviewSnapshotProvider
 Ticket string
 Scope previewTicketScope
 FieldID string
}

func(a *backendLivePreviewAuthority) check() error {
 denied:=errors.New("Wacom backend session revoked or unavailable")
 if a==nil||a.Backend==nil||a.Ticket==""||a.FieldID!="borrower_signature"{
  return denied
 }
 ctx,cancel:=context.WithTimeout(context.Background(),wacomRevocationRequestTimeout)
 defer cancel()
 state,err:=a.Backend.FetchPreviewSnapshot(ctx,a.Ticket)
 if err!=nil||ctx.Err()!=nil{return denied}
 if state.CompanyID!=a.Scope.CompanyID||
  state.OperatorID!=a.Scope.OperatorID||
  state.ContractID!=a.Scope.ContractID||
  state.ContractHash!=a.Scope.ContractHash||
  state.SessionID!=a.Scope.SessionID||
  state.WorkstationID!=a.Scope.WorkstationID||
  state.SessionKey!=a.Scope.SessionID||
  state.FieldID!=a.FieldID{
  return denied
 }
 return nil
}

func(a *backendLivePreviewAuthority) CheckPreviewActive(scope previewTicketScope) error {
 if a==nil||scope!=a.Scope{return errors.New("Wacom session scope changed")}
 return a.check()
}

func(a *backendLivePreviewAuthority) AuthenticatedWorkstationID()(string,error){
 if err:=a.check();err!=nil{return "",err}
 return a.Scope.WorkstationID,nil
}
