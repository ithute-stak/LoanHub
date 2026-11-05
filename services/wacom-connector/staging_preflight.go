package main

// Offline staging readiness checks. This command neither connects to the
// backend nor opens the Wacom tablet or preview socket. A local PASS is
// never evidence of backend enrollment, certificate authorization or
// legally effective signing.
import (
 "crypto/tls"
 "encoding/json"
 "errors"
 "io"
 "os"
 "path/filepath"
)

const maxWacomPreflightConfigBytes=4096

type wacomStagingPreflightConfig struct {
 IdentityDirectory string `json:"identity_directory"`
 TrustBundlePath string `json:"trust_bundle_path"`
 ReplayDirectory string `json:"replay_directory"`
 BackendCAPath string `json:"backend_ca_path"`
 ClientCertificatePath string `json:"client_certificate_path"`
 ClientKeyPath string `json:"client_key_path"`
 SDKExecutable string `json:"sdk_executable"`
 Calibration deviceCalibration `json:"-"`
 CalibrationMaxX int `json:"calibration_max_x"`
 CalibrationMaxY int `json:"calibration_max_y"`
 CalibrationMaxPressure int `json:"calibration_max_pressure"`
}

func loadWacomStagingPreflightConfig(path string)(wacomStagingPreflightConfig,error){
 denied:=errors.New("Wacom staging preflight configuration unavailable")
 var empty wacomStagingPreflightConfig
 if !filepath.IsAbs(path)||filepath.Clean(path)!=path{return empty,denied}
 info,err:=os.Lstat(path)
 if err!=nil||!info.Mode().IsRegular()||info.Mode().Perm()&0077!=0||
  info.Size()<=0||info.Size()>maxWacomPreflightConfigBytes||
  !ownedByConnectorUser(info){return empty,denied}
 f,err:=os.Open(path)
 if err!=nil{return empty,denied}
 defer f.Close()
 dec:=json.NewDecoder(io.LimitReader(f,maxWacomPreflightConfigBytes+1))
 dec.DisallowUnknownFields()
 var cfg wacomStagingPreflightConfig
 if dec.Decode(&cfg)!=nil{return empty,denied}
 var extra any
 if dec.Decode(&extra)!=io.EOF{return empty,denied}
 return cfg,nil
}

// checkLocalWacomStagingReadiness deliberately makes no network calls and
// never runs SDK pen capture. It confirms *only* locally configured
// prerequisites for later supervised activation.
func checkLocalWacomStagingReadiness(cfg wacomStagingPreflightConfig)error{
 denied:=errors.New("Wacom staging prerequisites not satisfied")
 id,private,err:=loadWorkstationIdentity(cfg.IdentityDirectory)
 if err!=nil{return denied}
 defer func(){for i:=range private{private[i]=0}}()
 backendKeys,err:=loadTrustedBackendPreviewKeys(cfg.IdentityDirectory)
 if err!=nil||len(backendKeys)==0{return denied}
 previewKeys,err:=loadPinnedWacomPreviewKeys(cfg.TrustBundlePath)
 if err!=nil||len(previewKeys)!=len(backendKeys){return denied}
 for kid,key:=range backendKeys{
  signed,ok:=previewKeys[kid]
  if !ok||len(signed)!=len(key){return denied}
  for i:=range key{if signed[i]!=key[i]{return denied}}
 }
 for _,path:=range []string{cfg.BackendCAPath,cfg.ClientCertificatePath,cfg.ClientKeyPath}{
  if !filepath.IsAbs(path)||filepath.Clean(path)!=path{return denied}
 }
 cert,err:=tls.LoadX509KeyPair(cfg.ClientCertificatePath,cfg.ClientKeyPath)
 if err!=nil{return denied}
 rootPEM,err:=os.ReadFile(cfg.BackendCAPath)
 if err!=nil||len(rootPEM)==0||len(rootPEM)>16384{return denied}
 backend,err:=newHardenedWacomIntrospectionClient(
  "https://loanhub.co.ls"+wacomIntrospectionPath,rootPEM,cert)
 if err!=nil{return denied}
 info,err:=os.Lstat(cfg.SDKExecutable)
 if err!=nil||!info.Mode().IsRegular()||info.Mode().Perm()&0111==0||
  !filepath.IsAbs(cfg.SDKExecutable)||filepath.Clean(cfg.SDKExecutable)!=cfg.SDKExecutable||
  !safeSamplePath.MatchString(cfg.SDKExecutable){return denied}
 calibration:=deviceCalibration{
  MinX:0,MaxX:cfg.CalibrationMaxX,
  MinY:0,MaxY:cfg.CalibrationMaxY,
  MaxPressure:cfg.CalibrationMaxPressure,
 }
 _,err=newProtectedWacomPreviewAuthority(wacomProtectedPreviewConfig{
  Backend:backend,WorkstationID:id,SDKExecutable:cfg.SDKExecutable,
  ReplayDirectory:cfg.ReplayDirectory,PinnedKeys:previewKeys,
  Calibration:calibration,
 })
 if err!=nil{return denied}
 return nil
}
