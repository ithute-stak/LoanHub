package main

// Production-intended dependency construction for a SINGLE enrolled
// workstation. This constructor does not mount HTTP routes or enable SDK
// capture; it refuses missing security dependencies and uses the existing
// filesystem-backed atomic replay store instead of an in-memory fake.
import (
 "crypto/ed25519"
 "errors"
 "path/filepath"
)

type wacomProtectedPreviewConfig struct {
 Backend *hardenedWacomIntrospectionClient
 WorkstationID string
 SDKExecutable string
 ReplayDirectory string
 PinnedKeys map[string]ed25519.PublicKey
 Calibration deviceCalibration
}

func newProtectedWacomPreviewAuthority(
 cfg wacomProtectedPreviewConfig,
)(verifiedWacomWebSocketAuthority,error){
 denied:=errors.New("Wacom protected preview dependencies unavailable")
 if cfg.Backend==nil||cfg.Backend.client==nil||
  !validUUID(cfg.WorkstationID)||
  !filepath.IsAbs(cfg.SDKExecutable)||
  filepath.Clean(cfg.SDKExecutable)!=cfg.SDKExecutable||
  !safeSamplePath.MatchString(cfg.SDKExecutable)||
  len(cfg.PinnedKeys)==0||!cfg.Calibration.valid(){
  return verifiedWacomWebSocketAuthority{},denied
 }
 for kid,pub:=range cfg.PinnedKeys {
  if kid==""||len(kid)>64||len(pub)!=ed25519.PublicKeySize{
   return verifiedWacomWebSocketAuthority{},denied
  }
 }
 replay,err:=newFilePreviewReplayStore(cfg.ReplayDirectory)
 if err!=nil{return verifiedWacomWebSocketAuthority{},denied}
 resolver:=mtlsWacomPreviewResolver{
  Backend:cfg.Backend,
  TrustedWorkstationID:cfg.WorkstationID,
  TrustedSDKExecutable:cfg.SDKExecutable,
  Keys:cfg.PinnedKeys,
  // The resolver constructs live backend-check providers after receiving
  // a verified snapshot. Never use a cached or fake authorization source.
  Enrollment:unconfiguredWacomAuthority{},
  Session:unconfiguredWacomAuthority{},
  Replay:replay,
  Calibration:cfg.Calibration,
 }
 return verifiedWacomWebSocketAuthority{Resolver:resolver,TrustedSDKExecutable:cfg.SDKExecutable},nil
}

// Fail-closed markers satisfy the existing legacy resolver constructor
// until its now-redundant static authority inputs can be removed. They are
// never exposed: the resolver replaces them with backendLivePreviewAuthority.
type unconfiguredWacomAuthority struct {}
func(unconfiguredWacomAuthority) AuthenticatedWorkstationID()(string,error){
 return "",errors.New("unconfigured workstation")
}
func(unconfiguredWacomAuthority) CheckPreviewActive(_ previewTicketScope)error{
 return errors.New("unconfigured session")
}
