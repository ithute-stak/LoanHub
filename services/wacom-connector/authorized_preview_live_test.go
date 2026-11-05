package main

import (
 "context"
 "errors"
 "testing"
)

type capturingLiveSink struct {
 liveFrames int
 finalFrames int
 firstPoints int
 failLive bool
}
func (s *capturingLiveSink) DeliverLivePreview(ctx context.Context, _ previewTicketScope, strokes [][]previewPoint) error {
 if err:=ctx.Err();err!=nil{return err}
 if s.failLive {return errors.New("client disconnected")}
 s.liveFrames++
 for _,stroke:=range strokes{s.firstPoints+=len(stroke)}
 return nil
}
func (s *capturingLiveSink) DeliverPreview(ctx context.Context,_ previewTicketScope,strokes [][]previewPoint) error {
 if err:=ctx.Err();err!=nil{return err}
 s.finalFrames++
 return nil
}
func TestAuthorizedPreviewStreamsValidatedSDKReports(t *testing.T){
 ticket,scope,now,cfg,source,_:=authorizedTestConfig(t)
 live:=&capturingLiveSink{}
 cfg.Sink=live
 if err:=runEphemeralAuthorizedPreview(context.Background(),ticket,scope,now,cfg);err!=nil{t.Fatal(err)}
 if live.liveFrames<1||live.finalFrames!=1||live.firstPoints<2{
  t.Fatalf("missing stream or final preview: live=%d final=%d points=%d",live.liveFrames,live.finalFrames,live.firstPoints)
 }
 if !source.called{t.Fatal("capture source not used")}
}
func TestAuthorizedPreviewLiveWriteFailureStopsCapture(t *testing.T){
 ticket,scope,now,cfg,_,_:=authorizedTestConfig(t)
 live:=&capturingLiveSink{failLive:true}
 cfg.Sink=live
 if err:=runEphemeralAuthorizedPreview(context.Background(),ticket,scope,now,cfg);err==nil{
  t.Fatal("disconnected stream accepted")
 }
 if live.finalFrames!=0{t.Fatal("final preview delivered after live sink failure")}
}
func TestAuthorizedPreviewRevokedBeforeFirstLiveFrame(t *testing.T){
 ticket,scope,now,cfg,source,_:=authorizedTestConfig(t)
 cfg.Admission.Session.(*testLivePreviewSession).rejectAt=1
 live:=&capturingLiveSink{}
 cfg.Sink=live
 if err:=runEphemeralAuthorizedPreview(context.Background(),ticket,scope,now,cfg);err==nil{t.Fatal("revoked capture admitted")}
 if source.called||live.liveFrames!=0||live.finalFrames!=0{t.Fatal("revoked preview touched SDK or browser")}
}
