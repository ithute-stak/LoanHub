package main

import (
    "fmt"
    "time"
)

// Local-only, disposable calibration + stroke diagnostic. It executes the
// official SDK query to completion *before* opening simpleInterface, so both
// vendor processes never compete for the same USB interface. No raw point,
// image, contract ID or borrower data leaves process memory.
type calibratedStrokeSummary struct {
    Calibration deviceCalibration
    PenReports int
    ContactPoints int
    Strokes int
    PreviewPoints int
}

func finishCalibratedTest(buffer *localStrokeBuffer, calibration deviceCalibration, reports int) (calibratedStrokeSummary, error) {
    if buffer == nil { return calibratedStrokeSummary{}, fmt.Errorf("missing local capture buffer") }
    strokes, err := buffer.finish()
    if err != nil { return calibratedStrokeSummary{}, fmt.Errorf("test strokes incomplete: %w", err) }
    preview, err := toPreviewStrokes(strokes, calibration)
    if err != nil { return calibratedStrokeSummary{}, fmt.Errorf("invalid calibrated test strokes: %w", err) }
    count := 0
    for _, stroke := range preview { count += len(stroke) }
    return calibratedStrokeSummary{
        Calibration: calibration, PenReports: reports, ContactPoints: buffer.count,
        Strokes: len(preview), PreviewPoints: count,
    }, nil
}

func testCalibratedLocalStrokes(queryExecutable, sampleExecutable string, duration time.Duration) (calibratedStrokeSummary, error) {
    calibration, err := queryLocalSDKCalibration(queryExecutable)
    if err != nil { return calibratedStrokeSummary{}, fmt.Errorf("SDK capability check failed: %w", err) }
    var buffer localStrokeBuffer
    defer buffer.discard()
    reports, err := testWacomSampleWithHandler(sampleExecutable, duration, buffer.accept)
    if err != nil { return calibratedStrokeSummary{}, fmt.Errorf("SDK pen capture failed: %w", err) }
    return finishCalibratedTest(&buffer, calibration, reports)
}
