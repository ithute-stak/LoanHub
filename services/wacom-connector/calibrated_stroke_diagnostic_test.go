package main

import "testing"

func TestFinishCalibratedTestWithDeviceCapabilityFixture(t *testing.T) {
    // These are the actual bounds measured on the operator's STU-540,
    // but the pen points below are disposable synthetic test values.
    c := deviceCalibration{MaxX:10800, MaxY:6480, MaxPressure:1023}
    var buffer localStrokeBuffer
    defer buffer.discard()
    for _, p := range []penSample{
        {Ready:1, Switch:1, X:1000, Y:2000, Pressure:700, Time:1000, Sequence:1},
        {Ready:1, Switch:1, X:2000, Y:2400, Pressure:600, Time:1005, Sequence:2},
        {Ready:1, Switch:0, X:2000, Y:2400, Pressure:0, Time:1010, Sequence:3},
        {Ready:1, Switch:1, X:2500, Y:2600, Pressure:750, Time:1015, Sequence:4},
    } {
        if err:=buffer.accept(p);err!=nil {t.Fatal(err)}
    }
    got,err:=finishCalibratedTest(&buffer,c,4)
    if err!=nil {t.Fatal(err)}
    if got.Strokes!=2 || got.ContactPoints!=3 || got.PreviewPoints!=3 || got.PenReports!=4 {
        t.Fatalf("unexpected summary: %+v",got)
    }
}

func TestFinishCalibratedTestRejectsInvalidBounds(t *testing.T) {
    var buffer localStrokeBuffer
    defer buffer.discard()
    for _, p := range []penSample{
        {Ready:1,Switch:1,X:100,Y:100,Pressure:2000,Time:1000,Sequence:1},
        {Ready:1,Switch:1,X:200,Y:200,Pressure:100,Time:1005,Sequence:2},
    } {
        if err:=buffer.accept(p);err!=nil {t.Fatal(err)}
    }
    if _,err:=finishCalibratedTest(&buffer,deviceCalibration{MaxX:10800,MaxY:6480,MaxPressure:1023},2);err==nil {
        t.Fatal("invalid pressure should fail")
    }
}
