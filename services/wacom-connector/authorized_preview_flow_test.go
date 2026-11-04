package main

import (
    "context"
    "crypto/ed25519"
    "crypto/rand"
    "errors"
    "testing"
    "time"
)

type boundedPreviewSource struct {
    called bool
    reports []penSample
    onFinish func()
}
func (s *boundedPreviewSource) CollectPreview(ctx context.Context, accept func(penSample) error) error {
    s.called = true
    for _, p := range s.reports {
        if err := ctx.Err(); err != nil { return err }
        if err := accept(p); err != nil { return err }
    }
    if s.onFinish != nil { s.onFinish() }
    return nil
}

type guardedPreviewSink struct { delivered int; strokes [][]previewPoint }
func (s *guardedPreviewSink) DeliverPreview(ctx context.Context, scope previewTicketScope, strokes [][]previewPoint) error {
    if err := ctx.Err(); err != nil { return err }
    s.delivered++
    s.strokes = strokes
    return nil
}
func authorizedTestConfig(t *testing.T) (string, previewTicketScope, time.Time, authorizedPreviewConfig, *boundedPreviewSource, *guardedPreviewSink) {
    t.Helper()
    pub, priv, err := ed25519.GenerateKey(rand.Reader)
    if err != nil { t.Fatal(err) }
    now := time.Now().UTC().Truncate(time.Second)
    scope := testPreviewScope()
    token := previewTestToken(t, priv, now, scope)
    source := &boundedPreviewSource{reports: []penSample{
        {Ready:1, Switch:1, X:100, Y:100, Pressure:300, Time:100, Sequence:1},
        {Ready:1, Switch:1, X:200, Y:200, Pressure:500, Time:110, Sequence:2},
        {Ready:1, Switch:0, X:200, Y:200, Time:111, Sequence:3},
    }}
    sink := &guardedPreviewSink{}
    config := authorizedPreviewConfig{
        Admission: previewAdmissionDependencies{
            Keys:map[string]ed25519.PublicKey{"test-ed25519-key":pub},
            Enrollment:&testEnrolledWorkstation{id:scope.WorkstationID},
            Session:&testLivePreviewSession{},
            Replay:&fakePreviewReplay{used:map[string]bool{}},
        },
        Calibration:deviceCalibration{MinX:0,MaxX:10800,MinY:0,MaxY:6480,MaxPressure:1023},
        Source:source, Sink:sink, MaxDuration:5*time.Second,
    }
    return token,scope,now,config,source,sink
}
func TestAuthorizedPreviewDeliversOnlyAfterAllChecks(t *testing.T) {
    ticket,scope,now,cfg,src,sink := authorizedTestConfig(t)
    if err := runEphemeralAuthorizedPreview(context.Background(),ticket,scope,now,cfg);err!=nil {t.Fatal(err)}
    if !src.called || sink.delivered!=1 || len(sink.strokes)!=1 || len(sink.strokes[0])!=2 {
        t.Fatalf("unexpected preview: source=%v deliveries=%d",src.called,sink.delivered)
    }
    if err := runEphemeralAuthorizedPreview(context.Background(),ticket,scope,now,cfg);err==nil {
        t.Fatal("replayed ticket admitted")
    }
    if sink.delivered!=1 {t.Fatal("replay delivered preview")}
}
func TestPreviewRefusesUnenrolledDeviceBeforeTouchingSDK(t *testing.T) {
    ticket,scope,now,cfg,src,sink := authorizedTestConfig(t)
    cfg.Admission.Enrollment.(*testEnrolledWorkstation).id = "77777777-7777-7777-7777-777777777777"
    if err := runEphemeralAuthorizedPreview(context.Background(),ticket,scope,now,cfg);err==nil {t.Fatal("unenrolled accepted")}
    if src.called || sink.delivered!=0 {t.Fatal("SDK or sink used before authentication")}
}
func TestRevokedDuringCaptureCannotDeliverPreview(t *testing.T) {
    ticket,scope,now,cfg,src,sink := authorizedTestConfig(t)
    src.onFinish=func(){cfg.Admission.Session.(*testLivePreviewSession).rejectAt=1}
    if err := runEphemeralAuthorizedPreview(context.Background(),ticket,scope,now,cfg);err==nil {t.Fatal("revoked preview delivered")}
    if sink.delivered!=0 {t.Fatal("revoked frame reached sink")}
}
func TestPreviewRefusesExpiredOrCancelledContext(t *testing.T) {
    ticket,scope,now,cfg,src,sink := authorizedTestConfig(t)
    ctx,cancel:=context.WithCancel(context.Background());cancel()
    if err:=runEphemeralAuthorizedPreview(ctx,ticket,scope,now,cfg);!errors.Is(err,context.Canceled) {
        t.Fatalf("cancelled context returned %v",err)
    }
    if src.called || sink.delivered!=0 {t.Fatal("cancelled capture touched SDK")}
    ticket,scope,now,cfg,src,sink=authorizedTestConfig(t)
    if err:=runEphemeralAuthorizedPreview(context.Background(),ticket,scope,now.Add(31*time.Second),cfg);err==nil {
        t.Fatal("expired capture ticket accepted")
    }
    if src.called || sink.delivered!=0 {t.Fatal("expired capture touched SDK")}
}
