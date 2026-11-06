package main

// SDK-backed, context-cancellable pen source for a future authenticated,
// ticket-admitted preview lease. This type is NOT mounted on an HTTP route.
// Caller must validate the enrolled workstation, one-use ticket and current
// contract/session revocation state before constructing/using this source.
import (
    "context"
    "errors"
    "os"
    "path/filepath"
    "time"
)

const sdkPreviewCollectionWindow = 10 * time.Second
const sdkPreviewSafetyMargin = 2 * time.Second

type wacomSDKPreviewSource struct {
    Executable string
}

func (s wacomSDKPreviewSource) CollectPreview(ctx context.Context, onPen func(penSample) error) error {
    if ctx == nil || onPen == nil { return errors.New("Wacom preview lease/callback unavailable") }
    if err:=ctx.Err();err!=nil{return err}
    if !filepath.IsAbs(s.Executable) || !safeSamplePath.MatchString(s.Executable) {
        return errors.New("untrusted Wacom SDK pen executable")
    }
    info,err:=os.Stat(s.Executable)
    if err!=nil||!info.Mode().IsRegular()||info.Mode().Perm()&0111==0{
        return errors.New("Wacom SDK executable unavailable")
    }
    deadline,ok:=ctx.Deadline()
    if !ok {return errors.New("bounded capture lease required")}
    remaining:=time.Until(deadline)
    if remaining <= sdkPreviewSafetyMargin+time.Second {
        return errors.New("Wacom preview lease about to expire")
    }
    captureWindow:=sdkPreviewCollectionWindow
    if remaining-sdkPreviewSafetyMargin < captureWindow {
        captureWindow=remaining-sdkPreviewSafetyMargin
    }
    // Leave time after stopping the SDK for final eligibility, revocation
    // rechecks and bounded delivery. Only transmit from the trusted sink.
    _,err=testWacomSampleWithContext(ctx,s.Executable,captureWindow,onPen)
    if ctx.Err()!=nil {return ctx.Err()}
    return err
}
