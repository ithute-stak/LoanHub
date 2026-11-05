package main

import (
 "net/http"
 "net/http/httptest"
 "testing"
)

func TestStagingRouteMuxIsolatedFromProductionBrowserPort(t *testing.T){
 cfg:=makeStagingPreflightFixture(t)
 mux,err:=newWacomStagingPreviewMux(cfg)
 if err!=nil{t.Fatalf("secure local staging composition rejected: %v",err)}
 req:=httptest.NewRequest(http.MethodGet,
  "http://127.0.0.1:8766"+previewWebSocketPath,nil)
 req.Header.Set("Origin","https://loanhub.co.ls")
 w:=httptest.NewRecorder()
 mux.ServeHTTP(w,req)
 if w.Code!=http.StatusForbidden{
  t.Fatalf("staging port unexpectedly allows capture: %d",w.Code)
 }
 // Diagnostics process on 8765 is not touched by this composition.
 req=httptest.NewRequest(http.MethodGet,
  "http://127.0.0.1:8766/v1/device/status",nil)
 w=httptest.NewRecorder()
 mux.ServeHTTP(w,req)
 if w.Code!=http.StatusForbidden{
  t.Fatalf("diagnostic host unexpectedly accepted on staging port: %d",w.Code)
 }
}

func TestStagingRouteMuxRefusesIncompleteCredentials(t *testing.T){
 cfg:=makeStagingPreflightFixture(t)
 cfg.ClientKeyPath="/missing/private.key"
 if _,err:=newWacomStagingPreviewMux(cfg);err==nil{
  t.Fatal("missing TLS private key permitted protected route mount")
 }
 cfg=makeStagingPreflightFixture(t)
 cfg.CalibrationMaxPressure=0
 if _,err:=newWacomStagingPreviewMux(cfg);err==nil{
  t.Fatal("invalid SDK calibration permitted protected route mount")
 }
 cfg=makeStagingPreflightFixture(t)
 cfg.SDKExecutable="/missing/sdk"
 if _,err:=newWacomStagingPreviewMux(cfg);err==nil{
  t.Fatal("missing SDK executable permitted protected route mount")
 }
}
