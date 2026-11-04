package main

import (
    "errors"
    "math"
)

// Device calibration MUST be read from verified vendor SDK tablet
// capabilities. Never infer these maxima from the STU-540 model name or
// self-reported browser data. This converter never enables signing.
type deviceCalibration struct {
    MinX int
    MaxX int
    MinY int
    MaxY int
    MaxPressure int
}

// PreviewPoint is the server-compatible 640x240 coordinate and pressure
// representation. Device sequence is intentionally not exposed to browsers.
type previewPoint struct {
    X float64 `json:"x"`
    Y float64 `json:"y"`
    At int `json:"at"`
    Pressure float64 `json:"pressure"`
}

const previewWidth = 640.0
const previewHeight = 240.0

func (c deviceCalibration) valid() bool {
    return c.MinX >= 0 && c.MinY >= 0 &&
        c.MaxX > c.MinX && c.MaxY > c.MinY &&
        c.MaxPressure > 0 && c.MaxPressure <= 1000000 &&
        c.MaxX <= 1000000 && c.MaxY <= 1000000
}

func round3(v float64) float64 { return math.Round(v*1000) / 1000 }

// toPreviewStrokes is a pure transformation for a FUTURE authenticated,
// ephemeral preview. It does not store/upload or display a signature.
// The API will reject device capture without independently proven provenance.
func toPreviewStrokes(strokes [][]nativePenPoint, c deviceCalibration) ([][]previewPoint, error) {
    if !c.valid() { return nil, errors.New("verified tablet calibration required") }
    if len(strokes) == 0 || len(strokes) > maxLocalStrokes {
        return nil, errors.New("invalid stroke count")
    }

    first := strokes[0]
    if len(first) == 0 { return nil, errors.New("empty first stroke") }
    startTime := int64(first[0].Time)
    lastTime := startTime
    lastSequence := int64(-1)
    total := 0
    out := make([][]previewPoint, 0, len(strokes))
    for _, stroke := range strokes {
        if len(stroke) == 0 { return nil, errors.New("empty stroke") }
        points := make([]previewPoint, 0, len(stroke))
        for _, p := range stroke {
            total++
            if total > maxLocalPoints { return nil, errors.New("point budget exceeded") }
            if p.X < c.MinX || p.X > c.MaxX || p.Y < c.MinY || p.Y > c.MaxY ||
                p.Pressure < 0 || p.Pressure > c.MaxPressure {
                return nil, errors.New("point exceeds device capabilities")
            }
            tick := int64(p.Time)
            if tick < startTime || tick < lastTime || tick-startTime > maxLocalDuration {
                return nil, errors.New("invalid capture timestamp")
            }
            sequence := int64(p.Sequence)
            if sequence < 0 || (lastSequence >= 0 && sequence <= lastSequence) {
                return nil, errors.New("nonmonotonic pen sequence")
            }
            points = append(points, previewPoint{
                X: round3(float64(p.X-c.MinX) * previewWidth / float64(c.MaxX-c.MinX)),
                Y: round3(float64(p.Y-c.MinY) * previewHeight / float64(c.MaxY-c.MinY)),
                At: int(tick-startTime),
                Pressure: round3(float64(p.Pressure) / float64(c.MaxPressure)),
            })
            lastTime = tick
            lastSequence = sequence
        }
        out = append(out, points)
    }
    if total < 2 { return nil, errors.New("at least two contact samples required") }
    return out, nil
}
