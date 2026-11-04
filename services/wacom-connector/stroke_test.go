package main

import (
    "fmt"
    "time"
)

// Stroke-test is a PRIVATE, LOCAL, disposable SDK diagnostic only.
// Raw points never leave this function or get printed, uploaded, persisted,
// shown through HTTP, or used for legal contract signing.
type localStrokeSummary struct {
    PenReports int
    ContactPoints int
    Strokes int
}

func testLocalStrokes(executable string, duration time.Duration) (localStrokeSummary, error) {
    var buffer localStrokeBuffer
    defer buffer.discard()
    reports, err := testWacomSampleWithHandler(executable, duration, buffer.accept)
    if err != nil {
        return localStrokeSummary{}, err
    }
    strokes, err := buffer.finish()
    if err != nil { return localStrokeSummary{}, fmt.Errorf("no usable test strokes: %w", err) }
    return localStrokeSummary{PenReports: reports, ContactPoints: buffer.count, Strokes: len(strokes)}, nil
}
