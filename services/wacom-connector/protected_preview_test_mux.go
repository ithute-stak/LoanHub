package main

// Composition boundary for a future explicitly enabled physical Wacom
// integration test. This does NOT change the default diagnostic service or
// install routes in main.go. No unsigned token, fake session or mock SDK
// fallback is permitted here.
import (
 "errors"
 "net/http"
)

type protectedWacomPreviewServerConfig struct {
 IdentityDirectory string
 Authority wacomProtectedPreviewConfig
}

// newProtectedWacomPreviewTestMux only exposes hardware preview when BOTH
// the local backend-signed proof path and the complete independently
// authorized SDK/WebSocket authority can be built. It intentionally returns
// an error rather than starting a partially configured HTTP service.
func newProtectedWacomPreviewTestMux(
 cfg protectedWacomPreviewServerConfig,
)(http.Handler,error){
 denied:=errors.New("Wacom protected test preview is not ready")
 if cfg.IdentityDirectory==""{
  return nil,denied
 }
 localID,_,err:=loadWorkstationIdentity(cfg.IdentityDirectory)
 if err!=nil||localID!=cfg.Authority.WorkstationID{return nil,denied}
 keys,err:=loadTrustedBackendPreviewKeys(cfg.IdentityDirectory)
 if err!=nil||len(keys)==0{return nil,denied}
 // Independent key provisioning for challenge envelope and preview ticket
 // validation must match. Never silently trust keys from a browser.
 if len(keys)!=len(cfg.Authority.PinnedKeys){return nil,denied}
 for kid,key:=range keys {
  pinned,ok:=cfg.Authority.PinnedKeys[kid]
  if !ok||len(pinned)!=len(key){return nil,denied}
  for i:=range key {if key[i]!=pinned[i]{return nil,denied}}
 }
 authority,err:=newProtectedWacomPreviewAuthority(cfg.Authority)
 if err!=nil{return nil,denied}
 proof:=&localWacomChallengeProofHandler{
  IdentityDirectory:cfg.IdentityDirectory,
  TrustedBackendKeys:keys,
 }
 ws:=newLocalWacomWSServer(authority)
 mux:=http.NewServeMux()
 mux.HandleFunc("/v1/device/status",handler)
 mux.Handle(localWacomChallengeProofPath,proof)
 mux.Handle(previewWebSocketPath,ws)
 return mux,nil
}
