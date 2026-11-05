package main

import (
  "context"
  "errors"
  "testing"
  "time"
)

// The vendor SDK may be quiet for many seconds while the pen is lifted.
// Revocation must still stop the session rather than wait for a pen report.
type idlePreviewSource struct { started bool; stopped bool }
func (s *idlePreviewSource) CollectPreview(ctx context.Context, onPen func(penSample) error) error {
 s.started=true
 <-ctx.Done()
 s.stopped=true
 return ctx.Err()
}
func TestIdleCaptureRevocationStopsSDKWithoutPenEvents(t *testing.T) {
 ticket,scope,now,cfg,_,_:=authorizedTestConfig(t)
 source:=&idlePreviewSource{}
 cfg.Source=source
 cfg.MaxDuration=3*time.Second
 live:=&capturingLiveSink{}
 cfg.Sink=live
 session:=cfg.Admission.Session.(*testLivePreviewSession)
 // The first check permits admission. Subsequent watchdog checks must
 // cancel a silent SDK stream before the lease naturally expires.
 session.rejectAt=4
 start:=time.Now()
 err:=runEphemeralAuthorizedPreview(context.Background(),ticket,scope,now,cfg)
 if err==nil {t.Fatal("revoked silent capture completed successfully")}
 if !source.started||!source.stopped {t.Fatalf("SDK not cancelled: started=%t stopped=%t",source.started,source.stopped)}
 if time.Since(start)>2*time.Second {t.Fatal("idle revocation did not interrupt capture promptly")}
 if live.liveFrames!=0||live.finalFrames!=0 {t.Fatal("revoked stream delivered handwriting")}
}
func TestCancelledSilentSDKNeverDeliversStrokes(t *testing.T) {
 ticket,scope,now,cfg,_,_:=authorizedTestConfig(t)
 source:=&idlePreviewSource{}
 cfg.Source=source
 live:=&capturingLiveSink{}
 cfg.Sink=live
 ctx,cancel:=context.WithTimeout(context.Background(),400*time.Millisecond)
 defer cancel()
 err:=runEphemeralAuthorizedPreview(ctx,ticket,scope,now,cfg)
 if !errors.Is(err,context.DeadlineExceeded) {t.Fatalf("expected context timeout: %v",err)}
 if live.liveFrames!=0||live.finalFrames!=0 {t.Fatal("timed out stream delivered handwriting")}
}
