package main

// Disposable, operator-triggered STU-540 handwriting preview renderer.
// Converts official Wacom SDK pen reports into an in-memory PNG only.
// It does not upload, sign contracts, or save an image to disk.
import (
    "bytes"
    "crypto/sha256"
    "encoding/hex"
    "errors"
    "image"
    "image/color"
    "image/draw"
    "image/png"
    "math"
    "time"
)

const (
    wacomPreviewWidth = 640
    wacomPreviewHeight = 240
    wacomPreviewMaxBytes = 128_000
    wacomPreviewMaxSamples = 5_000
)

type disposableWacomPreview struct {
    PNG []byte
    SHA256 string
    ContactPoints int
    StrokeCount int
}

// previewInkPoint is a clamped, calibrated viewport coordinate.
type previewInkPoint struct { x, y int }

func wacomPreviewPoint(report penSample, calibration deviceCalibration) (previewInkPoint, bool) {
    if !calibration.valid() || report.Ready != 1 || report.Switch != 1 ||
        report.Pressure < 1 || report.Pressure > calibration.MaxPressure ||
        report.X < 0 || report.X > calibration.MaxX ||
        report.Y < 0 || report.Y > calibration.MaxY { return previewInkPoint{}, false }
    const margin = 12
    x := margin + int(math.Round(float64(report.X)*float64(wacomPreviewWidth-2*margin-1)/float64(calibration.MaxX)))
    y := margin + int(math.Round(float64(report.Y)*float64(wacomPreviewHeight-2*margin-1)/float64(calibration.MaxY)))
    return previewInkPoint{x:x,y:y}, true
}

func paintPreviewDot(img *image.RGBA, x,y int) {
    ink := color.RGBA{R:19,G:44,B:86,A:255}
    for dy:=-2;dy<=2;dy++ {
        for dx:=-2;dx<=2;dx++ {
            if dx*dx+dy*dy <= 4 {
                px,py:=x+dx,y+dy
                if image.Pt(px,py).In(img.Bounds()) { img.SetRGBA(px,py,ink) }
            }
        }
    }
}

func paintPreviewLine(img *image.RGBA, a,b previewInkPoint) {
    dx,dy:=b.x-a.x,b.y-a.y
    steps:=int(math.Max(math.Abs(float64(dx)),math.Abs(float64(dy))))
    if steps < 1 { paintPreviewDot(img,a.x,a.y); return }
    for i:=0;i<=steps;i++ {
        x:=a.x+dx*i/steps
        y:=a.y+dy*i/steps
        paintPreviewDot(img,x,y)
    }
}

// renderDisposableWacomPNG rejects empty or implausible capture streams and
// preserves stylus-up boundaries, so separate strokes never join.
func renderDisposableWacomPNG(reports []penSample, calibration deviceCalibration) (disposableWacomPreview,error) {
    var out disposableWacomPreview
    if !calibration.valid() || len(reports)==0 || len(reports)>wacomPreviewMaxSamples {
        return out,errors.New("invalid Wacom preview calibration or sample count")
    }
    img:=image.NewRGBA(image.Rect(0,0,wacomPreviewWidth,wacomPreviewHeight))
    draw.Draw(img,img.Bounds(),&image.Uniform{C:color.White},image.Point{},draw.Src)
    var prev previewInkPoint
    havePrev:=false
    uniquePoint:=false
    first:=previewInkPoint{}
    for _,report:=range reports {
        if report.Ready != 1 || report.Switch != 1 || report.Pressure == 0 {
            havePrev=false
            continue
        }
        p,ok:=wacomPreviewPoint(report,calibration)
        if !ok { return disposableWacomPreview{},errors.New("pen report outside calibrated device limits") }
        out.ContactPoints++
        if out.ContactPoints==1 { first=p }
        if p!=first { uniquePoint=true }
        if !havePrev {
            out.StrokeCount++
            paintPreviewDot(img,p.x,p.y)
        } else {
            paintPreviewLine(img,prev,p)
        }
        prev=p
        havePrev=true
    }
    if out.ContactPoints<3 || !uniquePoint || out.StrokeCount==0 {
        return disposableWacomPreview{},errors.New("insufficient genuine pen movement for preview")
    }
    var buf bytes.Buffer
    if err:=png.Encode(&buf,img);err!=nil { return disposableWacomPreview{},err }
    if buf.Len()>wacomPreviewMaxBytes {
        return disposableWacomPreview{},errors.New("preview exceeds LoanHub upload limit")
    }
    sum:=sha256.Sum256(buf.Bytes())
    out.PNG=buf.Bytes()
    out.SHA256=hex.EncodeToString(sum[:])
    return out,nil
}

// captureDisposableWacomPreview runs the already verified official SDK
// diagnostic pipeline, collecting pen reports in RAM for a one-shot preview.
// The caller must make this a human-initiated *test only* operation.
func captureDisposableWacomPreview(queryExecutable, penExecutable string) (disposableWacomPreview,error) {
    var empty disposableWacomPreview
    calibration,err:=queryLocalSDKCalibration(queryExecutable)
    if err!=nil {return empty,err}
    if !calibration.valid(){return empty,errors.New("Wacom SDK calibration invalid")}
    reports:=make([]penSample,0,256)
    _,err=testWacomSampleWithHandler(penExecutable,25*time.Second,func(report penSample)error{
        if len(reports)>=wacomPreviewMaxSamples {return errors.New("Wacom sample capture limit exceeded")}
        reports=append(reports,report)
        return nil
    })
    if err!=nil {return empty,err}
    result,err:=renderDisposableWacomPNG(reports,calibration)
    // Avoid retaining a second copy of raw reports beyond this call.
    for i:=range reports {reports[i]=penSample{}}
    return result,err
}
