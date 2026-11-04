package main

import (
    "errors"
    "fmt"
)

// Local-only native STU stroke assembly. The SDK's uncalibrated integer units
// remain unchanged: do not map to browser coordinates or sign a contract here.
const (
    maxLocalPoints = 10000
    maxLocalStrokes = 300
    maxLocalDuration = 120000
)

type nativePenPoint struct {
    X int
    Y int
    Pressure int
    Time int
    Sequence int
}

type localStrokeBuffer struct {
    strokes [][]nativePenPoint
    active []nativePenPoint
    count int
    firstTime int
    lastTime int
    lastSequence int
    initialized bool
    sealed bool
}

func (b *localStrokeBuffer) accept(report penSample) error {
    if b.sealed { return errors.New("capture already sealed") }
    if report.Ready != 1 { return nil }
    if report.Switch != 0 && report.Switch != 1 {
        return errors.New("invalid pen switch")
    }
    if report.Switch == 0 {
        b.finishStroke()
        return nil
    }
    if !b.initialized {
        b.initialized = true
        b.firstTime = report.Time
        b.lastTime = report.Time
        b.lastSequence = report.Sequence
    } else if report.Time < b.lastTime || report.Sequence <= b.lastSequence {
        return errors.New("nonmonotonic pen timing or sequence")
    }
    if report.Time-b.firstTime > maxLocalDuration {
        return errors.New("local pen capture exceeded maximum duration")
    }
    if b.count >= maxLocalPoints { return errors.New("local pen capture exceeded point limit") }
    if len(b.active) == 0 && len(b.strokes) >= maxLocalStrokes {
        return errors.New("local pen capture exceeded stroke limit")
    }
    b.active = append(b.active, nativePenPoint{
        X: report.X, Y: report.Y, Pressure: report.Pressure,
        Time: report.Time, Sequence: report.Sequence,
    })
    b.count++
    b.lastTime = report.Time
    b.lastSequence = report.Sequence
    return nil
}

func (b *localStrokeBuffer) finishStroke() {
    if len(b.active) > 0 {
        b.strokes = append(b.strokes, b.active)
        b.active = nil
    }
}

func (b *localStrokeBuffer) finish() ([][]nativePenPoint, error) {
    if b.sealed { return nil, errors.New("capture already sealed") }
    b.finishStroke()
    b.sealed = true
    if b.count < 2 { return nil, errors.New("insufficient pen samples") }
    if len(b.strokes) > maxLocalStrokes || b.count > maxLocalPoints {
        return nil, fmt.Errorf("capture exceeds configured limits")
    }
    return b.strokes, nil
}

// discard overwrites the buffer's point fields before releasing references.
// Go memory is managed; this is best-effort, not a guaranteed secure erase.
func (b *localStrokeBuffer) discard() {
    for _, stroke := range b.strokes {
        for i := range stroke { stroke[i] = nativePenPoint{} }
    }
    for i := range b.active { b.active[i] = nativePenPoint{} }
    b.strokes = nil
    b.active = nil
    b.count = 0
    b.sealed = true
}
