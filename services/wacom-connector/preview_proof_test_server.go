package main

// Explicit test-only HTTP composition: the ONLY newly mounted capability
// is proof of an authenticated backend-signed preview challenge. This mode
// never mounts the SDK capture WebSocket or sends handwriting to a browser.
import (
 "errors"
 "net"
 "net/http"
 "time"
)

func newLocalWacomProofTestMux(directory string)(http.Handler,error){
 if directory=="" {return nil,errors.New("Wacom proof identity directory required")}
 if _,_,err:=loadWorkstationIdentity(directory);err!=nil{
  return nil,errors.New("enrolled workstation identity unavailable")
 }
 keys,err:=loadTrustedBackendPreviewKeys(directory)
 if err!=nil{return nil,errors.New("pinned backend public key unavailable")}
 proof:=&localWacomChallengeProofHandler{
  IdentityDirectory:directory,TrustedBackendKeys:keys,
 }
 mux:=http.NewServeMux()
 mux.Handle(localWacomChallengeProofPath,proof)
 mux.HandleFunc("/v1/device/status",handler)
 // No /v1/preview/stream endpoint is installed here.
 return mux,nil
}

func serveLocalWacomProofTestOnly(directory string)error{
 mux,err:=newLocalWacomProofTestMux(directory)
 if err!=nil{return err}
 listener,err:=net.Listen("tcp4",listenAddr)
 if err!=nil{return err}
 defer listener.Close()
 server:=&http.Server{
  Handler:mux,ReadHeaderTimeout:3*time.Second,
  ReadTimeout:5*time.Second,WriteTimeout:5*time.Second,
  IdleTimeout:10*time.Second,MaxHeaderBytes:8192,
 }
 return server.Serve(listener)
}
