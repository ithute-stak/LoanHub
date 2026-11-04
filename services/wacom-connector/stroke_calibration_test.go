package main

import (
    "testing"
)

func calibratedTablet() deviceCalibration {
    // Synthetic device capabilities only; NOT actual STU-540 dimensions.
    return deviceCalibration{MinX:100, MaxX:10100, MinY:200, MaxY:10200, MaxPressure:1024}
}

func TestCalibratedStrokesPreserveShapeAndTime(t *testing.T) {
    data := [][]nativePenPoint{
        {{X:100,Y:200,Pressure:0,Time:1000,Sequence:1},
         {X:5100,Y:5200,Pressure:512,Time:1005,Sequence:2}},
        {{X:10100,Y:10200,Pressure:1024,Time:1010,Sequence:3}},
    }
    points, err := toPreviewStrokes(data, calibratedTablet())
    if err != nil { t.Fatal(err) }
    if len(points)!=2 || points[0][0].X!=0 || points[0][0].Y!=0 ||
        points[0][1].X!=320 || points[0][1].Y!=120 ||
        points[0][1].At!=5 || points[0][1].Pressure!=0.5 ||
        points[1][0].X!=640 || points[1][0].Y!=240 ||
        points[1][0].At!=10 || points[1][0].Pressure!=1 {
        t.Fatalf("unexpected preview transformation: %+v",points)
    }
}

func TestCalibrationMustBeExplicit(t *testing.T) {
    raw:=[][]nativePenPoint{{{X:100,Y:200,Pressure:1,Time:1000,Sequence:1},{X:101,Y:201,Pressure:2,Time:1005,Sequence:2}}}
    if _,err:=toPreviewStrokes(raw,deviceCalibration{});err==nil { t.Fatal("unknown SDK capabilities accepted") }
    if _,err:=toPreviewStrokes(raw,deviceCalibration{MinX:1,MaxX:1,MinY:0,MaxY:4,MaxPressure:100});err==nil { t.Fatal("zero width calibration accepted") }
}

func TestRejectsOutOfRangePressureAndCoordinates(t *testing.T) {
    calibration:=calibratedTablet()
    good:=nativePenPoint{X:101,Y:201,Pressure:512,Time:1000,Sequence:1}
    for _,invalid:=range []nativePenPoint{
        {X:10101,Y:201,Pressure:512,Time:1005,Sequence:2},
        {X:101,Y:201,Pressure:1025,Time:1005,Sequence:2},
        {X:99,Y:201,Pressure:512,Time:1005,Sequence:2},
    } {
        if _,err:=toPreviewStrokes([][]nativePenPoint{{good,invalid}},calibration);err==nil { t.Fatalf("accepted %+v",invalid) }
    }
}

func TestRejectsNonmonotonicSequenceAndTime(t *testing.T) {
    c:=calibratedTablet()
    good:=nativePenPoint{X:100,Y:200,Pressure:1,Time:1000,Sequence:1}
    for _,bad:=range []nativePenPoint{
        {X:101,Y:201,Pressure:1,Time:1005,Sequence:1},
        {X:101,Y:201,Pressure:1,Time:999,Sequence:2},
        {X:101,Y:201,Pressure:1,Time:121001,Sequence:2},
    } {
        if _,err:=toPreviewStrokes([][]nativePenPoint{{good,bad}},c);err==nil { t.Fatalf("accepted %+v",bad) }
    }
}

func TestRejectsEmptyOrSinglePointCapture(t *testing.T) {
    c:=calibratedTablet()
    for _,raw:=range [][][]nativePenPoint{
        {},
        {{}},
        {{{X:100,Y:200,Time:1000,Sequence:1}}},
    } {
        if _,err:=toPreviewStrokes(raw,c);err==nil { t.Fatalf("accepted insufficient capture") }
    }
}
