package main

// Translate an authenticated LoanHub introspection snapshot into the exact
// coordinator scope. This adapter is not an authorization bypass: it requires
// separately pinned signer keys, enrolled workstation identity, live backend
// session revalidation and durable atomic ticket consumption.
import (
 "context"
 "crypto/ed25519"
 "errors"
 "time"
)

type wacomPreviewSnapshotProvider interface {
 FetchPreviewSnapshot(ctx context.Context, ticket string)(backendWacomPreviewSnapshot,error)
}

// No default dependencies are provided. Test-only/in-memory replay or a
// stale cached Session authority must never be used in production.
type mtlsWacomPreviewResolver struct {
 Backend wacomPreviewSnapshotProvider
 TrustedWorkstationID string
 TrustedSDKExecutable string
 Keys map[string]ed25519.PublicKey
 Replay previewTicketReplayStore
 Calibration deviceCalibration
}

func(r mtlsWacomPreviewResolver) ResolveAuthorizedPreview(
 ctx context.Context,ticket string,
)(authoritativeWacomPreviewState,error){
 denied:=errors.New("Wacom backend session authority unavailable")
 if ctx==nil||ctx.Err()!=nil||r.Backend==nil||
  !validUUID(r.TrustedWorkstationID)||r.TrustedSDKExecutable==""||
  len(r.Keys)==0||r.Replay==nil||
  !r.Calibration.valid(){
  return authoritativeWacomPreviewState{},denied
 }
 snapshot,err:=r.Backend.FetchPreviewSnapshot(ctx,ticket)
 if err!=nil||ctx.Err()!=nil{return authoritativeWacomPreviewState{},denied}
 if !validUUID(snapshot.CompanyID)||!validUUID(snapshot.OperatorID)||
  !validUUID(snapshot.ContractID)||!validUUID(snapshot.SessionID)||
  !validUUID(snapshot.WorkstationID)||snapshot.WorkstationID!=r.TrustedWorkstationID||
  !isLowerHexSHA256(snapshot.ContractHash)||
  snapshot.SessionKey!=snapshot.SessionID||
  snapshot.FieldID!="borrower_signature"{
  return authoritativeWacomPreviewState{},denied
 }
 expected:=previewTicketScope{
  CompanyID:snapshot.CompanyID,OperatorID:snapshot.OperatorID,
  ContractID:snapshot.ContractID,ContractHash:snapshot.ContractHash,
  SessionID:snapshot.SessionID,WorkstationID:snapshot.WorkstationID,
 }
 if _,err=verifyPreviewTicketSignatureAndScope(ticket,r.Keys,expected,time.Now().UTC());err!=nil{
  return authoritativeWacomPreviewState{},denied
 }
 // The backend-backed providers perform a fresh mTLS introspection on
 // every revalidation. The underlying handler independently verifies the
 // current tenant, enrollment and session, including revocation.
 live:=&backendLivePreviewAuthority{Backend:r.Backend,Ticket:ticket,Scope:expected,FieldID:snapshot.FieldID}
 // Fail before making capture available when the live backend is offline.
 if err=live.check();err!=nil{return authoritativeWacomPreviewState{},denied}
 return authoritativeWacomPreviewState{
  Scope:expected,SessionKey:snapshot.SessionKey,FieldID:snapshot.FieldID,
  SDKExecutable:r.TrustedSDKExecutable,
  Calibration:r.Calibration,
  Admission:previewAdmissionDependencies{
   Keys:r.Keys,Enrollment:live,Session:live,Replay:r.Replay,
  },
 },nil
}
