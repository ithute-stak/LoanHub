package main

import (
    "testing"
)

func TestBridgeStrokesPreservePenUpBoundariesAndPressure(t *testing.T) {
    collector, err := newBridgeStrokeCollector(1000, 500, 100)
    if err != nil { t.Fatal(err) }
    points := []penSample{
        {Ready:1, Switch:1, Pressure:50, X:100, Y:100, Time:10},
        {Ready:1, Switch:1, Pressure:75, X:200, Y:150, Time:11},
        {Ready:1, Switch:0, Pressure:0},
        {Ready:1, Switch:1, Pressure:25, X:300, Y:200, Time:20},
        {Ready:1, Switch:1, Pressure:90, X:400, Y:250, Time:21},
    }
    for _, point := range points {
        if err := collector.Add(point); err != nil { t.Fatal(err) }
    }
    envelope, err := collector.Envelope()
    if err != nil { t.Fatal(err) }
    if envelope.Format != "loanhub-pen-strokes-v1" || len(envelope.Strokes) != 2 {
        t.Fatalf("expected two separated strokes, got %#v", envelope)
    }
    if envelope.Strokes[0][0].X != 0.1 || envelope.Strokes[1][1].Pressure != 0.9 {
        t.Fatalf("wrong normalized SDK coordinates: %#v", envelope)
    }
    if envelope.Strokes[1][0].Tick != 20 { t.Fatal("stroke timestamp altered") }
}

func TestBridgeStrokesDiscardIsolatedNoise(t *testing.T) {
    collector, _ := newBridgeStrokeCollector(1000, 500, 100)
    _ = collector.Add(penSample{Ready:1,Switch:1,Pressure:12,X:10,Y:20,Time:1})
    _ = collector.Add(penSample{Ready:1,Switch:0})
    if _, err := collector.Envelope(); err == nil {
        t.Fatal("a single pen contact is not a valid stroke")
    }
}

func TestBridgeStrokesRejectOutOfBounds(t *testing.T) {
    collector, _ := newBridgeStrokeCollector(1000, 500, 100)
    for _, point := range []penSample{
        {Ready:1,Switch:1,Pressure:101,X:10,Y:20,Time:1},
        {Ready:1,Switch:1,Pressure:1,X:1001,Y:20,Time:1},
        {Ready:1,Switch:1,Pressure:1,X:10,Y:501,Time:1},
    } {
        if err := collector.Add(point); err == nil {
            t.Fatal("invalid calibrated report accepted")
        }
    }
}

func TestBridgeStrokesMonotonicTicksForEqualReportTimes(t *testing.T) {
    collector, _ := newBridgeStrokeCollector(1000, 500, 100)
    for i:=0; i<3; i++ {
        if err := collector.Add(penSample{Ready:1,Switch:1,Pressure:50,X:200,Y:200,Time:40}); err != nil {
            t.Fatal(err)
        }
    }
    envelope, err := collector.Envelope()
    if err != nil { t.Fatal(err) }
    ticks := envelope.Strokes[0]
    if ticks[0].Tick != 40 || ticks[1].Tick != 41 || ticks[2].Tick != 42 {
        t.Fatalf("timestamps must increase for bridge protocol: %#v", ticks)
    }
}

func TestBridgeStrokesRejectExcessivePoints(t *testing.T) {
    collector, _ := newBridgeStrokeCollector(1000, 500, 100)
    for i:=0;i<8192;i++ {
        if err:=collector.Add(penSample{Ready:1,Switch:1,Pressure:50,X:100,Y:100,Time:i});err!=nil {
            t.Fatalf("point %d: %v",i,err)
        }
    }
    if err:=collector.Add(penSample{Ready:1,Switch:1,Pressure:50,X:100,Y:100,Time:8192});err==nil {
        t.Fatal("8193rd point must fail before buffering")
    }
}

func TestBridgeStrokesRequirePositiveCalibration(t *testing.T) {
    if _, err := newBridgeStrokeCollector(0, 500, 100); err == nil {
        t.Fatal("zero calibration cannot normalize data")
    }
}
