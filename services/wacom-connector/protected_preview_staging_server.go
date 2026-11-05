package main

// Explicit staging-only local listener. This does not replace the running
// diagnostics service on port 8765, and browsers must never be redirected
// to it by weakening origin/host checks. Capture will fail closed until
// production-grade backend mTLS, enrollment and signed-ticket authority
// have been independently provisioned.
import (
 "crypto/tls"
 "errors"
 "net"
 "net/http"
 "os"
 "io"
 "syscall"
 "time"
)

const wacomStagingPreviewListenAddr = "127.0.0.1:8766"

func readPrivateWacomStagingCA(path string)([]byte,error){
 if !privateWacomStagingMaterial(path){return nil,errors.New("untrusted TLS CA file")}
 file,err:=os.OpenFile(path,os.O_RDONLY|syscall.O_NOFOLLOW,0)
 if err!=nil{return nil,err}
 defer file.Close()
 data,err:=io.ReadAll(io.LimitReader(file,16385))
 if err!=nil||len(data)==0||len(data)>16384{return nil,errors.New("invalid TLS CA")}
 return data,nil
}

// A preflight PASS is necessary but not a claim of backend authorization.
// Both startup and HTTP mux assembly use the same protected authority.
func newWacomStagingPreviewMux(cfg wacomStagingPreflightConfig)(http.Handler,error){
 denied:=errors.New("Wacom staging preview prerequisites unavailable")
 if err:=checkLocalWacomStagingReadiness(cfg);err!=nil{return nil,denied}
 id,private,err:=loadWorkstationIdentity(cfg.IdentityDirectory)
 if err!=nil{return nil,denied}
 defer func(){for i:=range private{private[i]=0}}()
 keys,err:=loadPinnedWacomPreviewKeys(cfg.TrustBundlePath)
 if err!=nil{return nil,denied}
 cert,err:=tls.LoadX509KeyPair(cfg.ClientCertificatePath,cfg.ClientKeyPath)
 if err!=nil{return nil,denied}
 ca,err:=readPrivateWacomStagingCA(cfg.BackendCAPath)
 if err!=nil{return nil,denied}
 backend,err:=newHardenedWacomIntrospectionClient(
  "https://loanhub.co.ls"+wacomIntrospectionPath,ca,cert,
 )
 if err!=nil{return nil,denied}
 authority:=wacomProtectedPreviewConfig{
  Backend:backend,WorkstationID:id,SDKExecutable:cfg.SDKExecutable,
  ReplayDirectory:cfg.ReplayDirectory,PinnedKeys:keys,
  Calibration:deviceCalibration{
   MinX:0,MaxX:cfg.CalibrationMaxX,
   MinY:0,MaxY:cfg.CalibrationMaxY,
   MaxPressure:cfg.CalibrationMaxPressure,
  },
 }
 return newProtectedWacomPreviewTestMux(protectedWacomPreviewServerConfig{
  IdentityDirectory:cfg.IdentityDirectory,Authority:authority,
 })
}

// The staging hostname is intentionally NOT the production connector
// hostname. The WebSocket handler's exact Host guard remains pinned to
// 127.0.0.1:8765; therefore no browser capture can begin on :8766.
// This listener is for guarded route composition and negative tests only.
func serveProtectedWacomStagingPreview(configPath string)error{
 cfg,err:=loadWacomStagingPreflightConfig(configPath)
 if err!=nil{return errors.New("Wacom staging config unavailable")}
 handler,err:=newWacomStagingPreviewMux(cfg)
 if err!=nil{return errors.New("Wacom staging authority unavailable")}
 listener,err:=net.Listen("tcp4",wacomStagingPreviewListenAddr)
 if err!=nil{return err}
 defer listener.Close()
 server:=&http.Server{
  Handler:handler,ReadHeaderTimeout:3*time.Second,
  ReadTimeout:5*time.Second,WriteTimeout:15*time.Second,
  IdleTimeout:10*time.Second,MaxHeaderBytes:8192,
 }
 err=server.Serve(listener)
 if errors.Is(err,http.ErrServerClosed){return nil}
 return err
}
